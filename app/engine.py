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
SYSTEM_PROMPT = """You are an elite Senior RPA Incident Commander. You analyze broken RPA bot \
logs like a detective — methodically, step by step.

You have access to specialist tools. Use them in this order:

1. classify_error       → understand the error type first
2. extract_keywords     → get the key terms from the log
3. search_past_incidents → check if we've seen this before
4. suggest_selector_fix → if there are SAP UI selector errors, suggest fixes

Once you have all tool results, write a final structured incident report with:

🔍 ROOT CAUSE: What exactly went wrong and why.
🛠️ RECOMMENDED FIXES: Concrete, actionable steps. Include corrected SAP selectors if relevant.
📚 SIMILAR PAST INCIDENTS: Reference any past incidents found and what resolved them.
🏷️ CLASSIFICATION: Business Exception or System Exception — with clear justification.
⚡ PRIORITY: High / Medium / Low — with reasoning.

Be precise. Be actionable. No vague answers."""


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
