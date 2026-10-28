"""
engine.py — The brain of the project. Runs the Claude AI agentic loop.

WHAT THIS FILE DOES:
  1. Takes the log file text as input
  2. Sends it to Claude AI along with 4 tool definitions
  3. Claude decides which tools to call (classify, search, fix...)
  4. We run those tools and send results back to Claude
  5. Claude keeps looping until it has enough info
  6. Claude writes the final incident report
  7. We return that report

OLD WAY (simple, one-shot):
  log → one big prompt → Claude → answer (done in 1 step)

NEW WAY (agentic loop):
  log → Claude thinks → calls classify_error tool
                     → calls extract_keywords tool
                     → calls search_past_incidents tool
                     → calls suggest_selector_fix tool
                     → loops again if needed
                     → writes final report
"""

import json     # used to convert tool results to string before sending to Claude
import logging  # used to print debug/info messages during the loop
import os       # used to read environment variables like ANTHROPIC_API_KEY
from typing import Optional  # used for type hints

import anthropic           # official Anthropic SDK to talk to Claude AI
from dotenv import load_dotenv  # reads .env file and loads secrets into environment

from app.tools import TOOL_REGISTRY  # import the 4 specialist tool functions

# Load environment variables from .env file
# This makes ANTHROPIC_API_KEY available via os.getenv()
load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# ARIZE TRACING SETUP
# Arize is an LLMOps platform — it records every Claude call so you can see:
#   - What log was sent to Claude
#   - Which tools Claude called
#   - What the final report was
#   - How many tokens were used
#   - How long each call took
#
# This only activates if ARIZE_SPACE_ID and ARIZE_API_KEY are set in .env
# If not set — the app works normally, just without Arize tracking
# ──────────────────────────────────────────────────────────────────────────────
def _setup_arize():
    """
    Sets up Arize tracing if credentials are available.
    Called once when the module loads.
    """
    arize_space_id = os.getenv("ARIZE_SPACE_ID")
    arize_api_key  = os.getenv("ARIZE_API_KEY")

    if not arize_space_id or not arize_api_key:
        logging.getLogger(__name__).info(
            "Arize tracing disabled — ARIZE_SPACE_ID or ARIZE_API_KEY not set."
        )
        return

    try:
        from arize.otel import register
        from openinference.instrumentation.anthropic import AnthropicInstrumentor

        # Step 1: Register Arize — connects to Arize servers
        tracer_provider = register(
            space_id=arize_space_id,
            api_key=arize_api_key,
            project_name="genai-incident-commander",  # project name in Arize dashboard
        )

        # Step 2: Instrument Anthropic SDK — traces every Claude call automatically
        AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)

        logging.getLogger(__name__).info("Arize tracing enabled ✅")

    except Exception as exc:
        logging.getLogger(__name__).warning("Arize setup failed: %s", exc)


# Initialize Arize when this file loads
_setup_arize()

# Set up logger for this file
# Usage: logger.info("message") → prints with timestamp and level
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# CLAUDE CLIENT — Created once, reused for every request
# ──────────────────────────────────────────────────────────────────────────────
_client: Optional[anthropic.Anthropic] = None  # starts as None, created on first use


def _get_client() -> anthropic.Anthropic:
    """
    Creates the Claude AI client (connection to Anthropic's servers).

    Uses 'lazy singleton' pattern:
      - First time called → creates the client and saves it
      - Every time after → reuses the same client (faster, saves memory)

    Raises an error if ANTHROPIC_API_KEY is not set in .env
    """
    global _client  # refer to the module-level _client variable

    if _client is None:
        # Read API key from environment (loaded from .env file)
        api_key = os.getenv("ANTHROPIC_API_KEY")

        # If key is missing, raise a clear error message
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. "
                "Copy .env.example → .env and add your key."
            )

        # Create the Anthropic client with the API key
        _client = anthropic.Anthropic(api_key=api_key)

    return _client


# ──────────────────────────────────────────────────────────────────────────────
# MODEL NAME — Which Claude model to use
# Default: claude-opus-4-8 (most intelligent)
# Can be overridden by setting CLAUDE_MODEL in .env
# ──────────────────────────────────────────────────────────────────────────────
MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")


# ──────────────────────────────────────────────────────────────────────────────
# TOOL DEFINITIONS — Tells Claude what tools exist and how to use them
# Claude reads these descriptions and decides when to call each tool
# ──────────────────────────────────────────────────────────────────────────────
TOOLS: list[dict] = [
    {
        # Tool name — Claude uses this exact string to call the tool
        "name": "classify_error",

        # Description — Claude reads this to understand when to use this tool
        "description": (
            "Classify the RPA log error as 'Business Exception' or 'System Exception' "
            "using keyword analysis. Call this FIRST — it gives you the initial signal "
            "about what kind of failure this is."
        ),

        # Input schema — tells Claude what arguments to pass when calling this tool
        "input_schema": {
            "type": "object",
            "properties": {
                "log_text": {
                    "type": "string",
                    "description": "The full RPA log text to classify."
                }
            },
            "required": ["log_text"]  # log_text is mandatory
        }
    },
    {
        "name": "extract_keywords",
        "description": (
            "Extract the most important error keywords and error lines from the log. "
            "Call this after classify_error — the keywords are used for searching "
            "past incidents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "log_text": {
                    "type": "string",
                    "description": "The full RPA log text to extract keywords from."
                }
            },
            "required": ["log_text"]
        }
    },
    {
        "name": "search_past_incidents",
        "description": (
            "Search the incident knowledge base for similar past failures and their "
            "resolutions. Call this after extract_keywords to find relevant historical "
            "context that can inform the fix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords extracted from the log to search with."
                },
                "error_type": {
                    "type": "string",
                    "description": (
                        "The error classification (Business Exception / System Exception) "
                        "to narrow the search."
                    )
                }
            },
            "required": ["keywords"]  # keywords is mandatory, error_type is optional
        }
    },
    {
        "name": "suggest_selector_fix",
        "description": (
            "Scan the log for broken SAP UI selectors and suggest hardened replacements. "
            "Call this when you see UI element, selector, or 'Cannot find element' errors."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "log_text": {
                    "type": "string",
                    "description": "The full RPA log text to scan for broken selectors."
                }
            },
            "required": ["log_text"]
        }
    }
]


# ──────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT — Claude's personality and instructions
# This tells Claude HOW to behave and WHAT to include in the final report
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a Senior RPA Incident Commander writing reports for a MIXED audience — \
some readers are experienced UiPath developers, but most are business analysts, AP team members, \
SAP support staff, or managers who have never opened UiPath Studio in their life.

Your job: write a report so clear and step-by-step that ANY reader — even a non-technical person \
— can read it, understand exactly what happened, and know precisely what to do next WITHOUT needing \
to ask anyone for help.

STEP 1 — USE TOOLS IN THIS ORDER:
1. classify_error        → always call this first
2. extract_keywords      → always call this second
3. search_past_incidents → always call this third
4. suggest_selector_fix  → only call this if you see selector / UI element / "Cannot find" errors

STEP 2 — WRITE THE REPORT IN EXACTLY THIS FORMAT (no deviations):

NEVER start with phrases like "I have all the information" or "Here is the report".
Go straight into the report. Use the exact section headers below.

---

## ❌ WHAT WENT WRONG
Write 2-3 plain English sentences. Imagine explaining to someone who has never seen a bot before.
- Sentence 1: What the bot was trying to do
- Sentence 2: What went wrong and where it stopped
- Sentence 3: What the business impact is (which invoice/vendor/transaction is now stuck)
Example: "The bot was processing invoice INV-2024-001 in SAP. It failed because the Save button on the screen has changed and the bot could not find it. Invoice INV-2024-001 is now unprocessed and needs manual attention."

## 🏷️ ERROR TYPE
State ONLY one of these two: **Business Exception** or **System Exception**
Then explain it in plain English for a non-technical reader:
- If Business Exception: "This means the bot itself is working fine. The problem is with the DATA — for example, a vendor that does not exist, a duplicate invoice, or a blocked payment. The RPA team does not need to change anything in the bot. The business team needs to fix the data."
- If System Exception: "This means something TECHNICAL broke — for example, a button on the screen moved, the SAP system timed out, or the network dropped. The bot could not see what it was looking for. The RPA developer needs to fix the bot or the environment."

## ⚡ PRIORITY
State ONLY one of: 🔴 HIGH / 🟡 MEDIUM / 🟢 LOW
Then write TWO lines:
- Line 1: Why this priority level was chosen
- Line 2: What happens if nobody fixes this today (business consequence)
Example: "🔴 HIGH — The SAP Save button selector is broken, meaning ALL future invoices processed by this bot will fail, not just this one. If not fixed today, the entire invoice processing queue will pile up."

## 🔍 ROOT CAUSE — WHAT EXACTLY HAPPENED
Write 4-6 bullet points. Each bullet must be one complete sentence that a non-technical person can understand.
- Start with WHAT failed (name the exact field, button, vendor, invoice, transaction code)
- Then WHERE it failed (which step, which SAP screen, which queue)
- Then quote the EXACT line from the log that proves it (in plain quotes, not code)
- Then WHY it failed (data missing? screen changed? network issue? duplicate?)
- Then WHO or WHAT caused this (SAP upgrade? wrong data entry? vendor blocked by finance?)
Avoid abbreviations. Write "SAP transaction VA01 (Sales Order Creation)" not just "VA01".

## 🛠️ HOW TO FIX IT — STEP BY STEP
This is the most important section. Write numbered steps so clear that the reader can follow them WITHOUT any prior knowledge of UiPath or SAP.

For each step:
- Start with WHO needs to do this (e.g., "AP Team", "SAP Basis Team", "RPA Developer", "Finance Manager")
- Then WHAT exactly they need to do — be specific, name the exact system, screen, field, or button
- Then HOW to verify it worked

Format:
**Step 1 — [Team Name]**
What to do: [Exact action — open which system, go to which screen, click what, enter what value]
How to verify: [What they should see if it worked]
Estimated time: [e.g., 5 minutes / 1 hour / next business day]

**Step 2 — [Team Name]**
...

Write maximum 5 steps. Every step must be actionable RIGHT NOW — no vague steps like "investigate" or "check the logs".

## ✅ HOW TO PREVENT THIS IN FUTURE
2-3 bullet points. Simple preventive actions anyone can understand.
- Example: "AP Team to verify vendor exists in SAP before submitting to the bot queue"
- Example: "RPA Developer to add a dynamic selector for the Save button so it works even after SAP upgrades"
- Example: "SAP Basis Team to notify RPA team 48 hours before any SAP screen layout changes"

## 📚 SIMILAR PAST INCIDENTS
List matching past incidents found. Format each as:
- **INC-XXX** — [plain English description of what happened] → [what fixed it] → [Is the fix the same here? Yes/No — explain in one sentence why]
If no past incidents found, write: "No similar incidents found in the knowledge base. This may be a new type of failure — document the resolution once fixed so future occurrences are handled faster."

## 🤖 BOT STATUS RIGHT NOW
Write 2 lines:
- Line 1: Is the bot currently running, paused, or fully stopped?
- Line 2: Which transactions/invoices are affected — only this one or all of them?
Example: "The bot has stopped processing and moved this transaction to the exception queue. All other invoices in the queue are unaffected and will be processed normally."

---

GOLDEN RULES:
- Write every sentence as if the reader has never used UiPath, SAP, or any RPA tool
- NEVER use unexplained abbreviations — always write the full name at least once
- Every action step must name a SPECIFIC person/team, a SPECIFIC system, and a SPECIFIC action
- If you mention a selector, explain what a selector is in plain English in brackets: (a selector is the address the bot uses to find a button or field on the screen)
- Bold the single most important word or finding in each section
- The FIX IT section must be so clear that someone can follow it on their first day on the job"""


# ──────────────────────────────────────────────────────────────────────────────
# MAIN FUNCTION — The Agentic Loop
# ──────────────────────────────────────────────────────────────────────────────
def run_agent(log_text: str) -> dict:
    """
    Runs the full Claude agentic loop on an RPA log file.

    HOW THE LOOP WORKS:
      Step 1: Send log to Claude with tool definitions
      Step 2: Claude responds with a tool call request
      Step 3: We run that tool and get the result
      Step 4: Send the result back to Claude
      Step 5: Claude either calls another tool OR writes the final report
      Step 6: Repeat until Claude says it's done (stop_reason = "end_turn")

    Args:
      log_text: The full text content of the RPA log file

    Returns a dictionary with:
      final_report → The complete incident analysis written by Claude
      agent_steps  → List of every tool Claude called (for transparency)
      iterations   → How many loops it took to complete
    """

    # Get the Claude client (creates it if first time)
    client = _get_client()

    # Start the conversation with the user's log file
    messages = [
        {"role": "user", "content": f"Analyze this RPA log:\n\n{log_text}"}
    ]

    tool_calls_log: list[dict] = []  # track every tool Claude calls
    max_iterations = 10              # safety limit — stop after 10 loops
    iteration = 0                    # current loop count

    logger.info("Starting Claude agentic loop (model=%s)", MODEL)

    # ── THE LOOP ──────────────────────────────────────────────────────────────
    while iteration < max_iterations:
        iteration += 1
        logger.debug("Agent iteration %d", iteration)

        # Send current conversation to Claude
        # Claude reads the messages and decides what to do next
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,       # maximum length of Claude's response
            system=SYSTEM_PROMPT,  # Claude's instructions/personality
            tools=TOOLS,           # the 4 tools Claude can call  # type: ignore[arg-type]
            messages=messages,     # full conversation history     # type: ignore[arg-type]
        )

        logger.debug("stop_reason=%s", response.stop_reason)

        # ── CASE 1: Claude is done — no more tools needed ─────────────────────
        # stop_reason = "end_turn" means Claude finished writing the report
        if response.stop_reason == "end_turn":

            # Extract the text from Claude's response
            final_text = "".join(
                block.text
                for block in response.content
                if block.type == "text"  # only take text blocks, not tool_use blocks
            )

            logger.info(
                "Agent finished in %d iterations, %d tool calls",
                iteration,
                len(tool_calls_log)
            )

            # Return the final result
            return {
                "final_report": final_text,
                "agent_steps": tool_calls_log,
                "iterations": iteration,
            }

        # ── CASE 2: Claude wants to call a tool ───────────────────────────────
        # stop_reason = "tool_use" means Claude is requesting a tool call
        if response.stop_reason == "tool_use":

            # Add Claude's response (with tool request) to conversation history
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []  # collect results from all tools Claude requested

            # Loop through Claude's response blocks
            for block in response.content:

                # Only process tool_use blocks (skip text blocks)
                if block.type != "tool_use":
                    continue

                tool_name = block.name    # e.g. "classify_error"
                tool_args = block.input   # arguments Claude wants to pass (already a dict)
                tool_use_id = block.id    # unique ID for this specific tool call

                logger.debug("Calling tool: %s(%s)", tool_name, json.dumps(tool_args)[:120])

                # Save this tool call to our log (shown in API response)
                tool_calls_log.append({"tool": tool_name, "args": tool_args})

                # Look up the tool function in TOOL_REGISTRY and run it
                if tool_name in TOOL_REGISTRY:
                    try:
                        # Call the actual Python function with the args Claude provided
                        result = TOOL_REGISTRY[tool_name](**tool_args)

                        # Convert result dict to JSON string to send back to Claude
                        result_str = json.dumps(result, indent=2)

                    except Exception as exc:
                        # If tool crashed, send error message back to Claude
                        logger.warning("Tool %s raised: %s", tool_name, exc)
                        result_str = json.dumps({"error": str(exc)})
                else:
                    # Claude called a tool that doesn't exist
                    result_str = json.dumps({"error": f"Unknown tool: {tool_name}"})

                # Package the result in Anthropic's required format
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,  # matches Claude's tool call ID
                    "content": result_str,        # the tool's output
                })

            # Send all tool results back to Claude as a user message
            # Claude will read these and decide what to do next
            messages.append({"role": "user", "content": tool_results})
            continue  # go back to top of loop — ask Claude again

        # ── CASE 3: Unexpected stop reason ────────────────────────────────────
        # This shouldn't happen but handle it gracefully
        logger.warning("Unexpected stop_reason=%s, returning as final.", response.stop_reason)
        final_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        return {
            "final_report": final_text or "Agent stopped unexpectedly.",
            "agent_steps": tool_calls_log,
            "iterations": iteration,
        }

    # ── LOOP LIMIT REACHED ────────────────────────────────────────────────────
    # Claude didn't finish within 10 iterations — return a warning
    logger.error("Agent hit max_iterations=%d without completing.", max_iterations)
    return {
        "final_report": (
            "⚠️ Agent reached the maximum iteration limit without completing the analysis. "
            "The log may be too complex or malformed."
        ),
        "agent_steps": tool_calls_log,
        "iterations": iteration,
    }


# ──────────────────────────────────────────────────────────────────────────────
# BACKWARD COMPATIBLE WRAPPER
# The old /analyze endpoint expects just a string (not a dict)
# This wrapper calls run_agent() and returns only the final_report text
# ──────────────────────────────────────────────────────────────────────────────
def analyze_rpa_logs(log_text: str) -> str:
    """Simple wrapper — returns only the final report text (not the full dict)."""
    return run_agent(log_text)["final_report"]
