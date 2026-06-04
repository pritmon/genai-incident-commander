"""
engine.py — Agentic RPA Log Analyzer powered by Claude (Anthropic SDK).

HOW THE AGENTIC LOOP WORKS:
  1. We send the log to Claude with a set of tool definitions
  2. Claude decides which tools to call (classify, search past incidents, fix selectors…)
  3. We execute each tool and send the results back to Claude
  4. Claude loops until it has enough info, then writes the final report

OLD WAY (Gemini one-shot):
  log → one big prompt → answer

NEW WAY (Claude agentic):
  log → Claude thinks → calls classify_error
             → calls extract_keywords
             → calls search_past_incidents
             → calls suggest_selector_fix
             → loops until confident
             → final structured incident report
"""

import json
import logging
import os
from typing import Optional

import anthropic
from dotenv import load_dotenv

from app.tools import TOOL_REGISTRY

load_dotenv()

logger = logging.getLogger(__name__)

# ── Client ────────────────────────────────────────────────────────────────────
_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    """Lazy singleton — created once, reused on every request."""
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. "
                "Copy .env.example → .env and add your key."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ── Model ─────────────────────────────────────────────────────────────────────
MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")

# ── Tool declarations (Anthropic tool-use format) ─────────────────────────────
TOOLS: list[dict] = [
    {
        "name": "classify_error",
        "description": (
            "Classify the RPA log error as 'Business Exception' or 'System Exception' "
            "using keyword analysis. Call this FIRST — it gives you the initial signal "
            "about what kind of failure this is."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "log_text": {
                    "type": "string",
                    "description": "The full RPA log text to classify."
                }
            },
            "required": ["log_text"]
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
            "required": ["keywords"]
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

# ── System prompt ─────────────────────────────────────────────────────────────
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


# ── Agentic loop ─────────────────────────────────────────────────────────────
def run_agent(log_text: str) -> dict:
    """
    Run the Claude agentic loop on an RPA log.

    Claude decides which tools to call. We execute them and feed results back.
    Loop continues until Claude stops requesting tools and writes the final report.

    Returns:
        {
            "final_report": str,        # The full incident analysis
            "agent_steps": list[dict],  # Every tool Claude called
            "iterations": int           # How many loops it took
        }
    """
    client = _get_client()
    messages = [
        {"role": "user", "content": f"Analyze this RPA log:\n\n{log_text}"}
    ]

    tool_calls_log: list[dict] = []
    max_iterations = 10
    iteration = 0

    logger.info("Starting Claude agentic loop (model=%s)", MODEL)

    while iteration < max_iterations:
        iteration += 1
        logger.debug("Agent iteration %d", iteration)

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,              # type: ignore[arg-type]
            messages=messages,        # type: ignore[arg-type]
        )

        logger.debug("stop_reason=%s", response.stop_reason)

        # ── No more tool calls → Claude is done, return final answer ──────────
        if response.stop_reason == "end_turn":
            final_text = "".join(
                block.text
                for block in response.content
                if block.type == "text"
            )
            logger.info(
                "Agent finished in %d iterations, %d tool calls",
                iteration,
                len(tool_calls_log)
            )
            return {
                "final_report": final_text,
                "agent_steps": tool_calls_log,
                "iterations": iteration,
            }

        # ── Claude wants to call tools ─────────────────────────────────────────
        if response.stop_reason == "tool_use":
            # Append Claude's response (with tool_use blocks) to history
            messages.append({"role": "assistant", "content": response.content})

            # Execute each requested tool and collect results
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_args = block.input   # already a dict
                tool_use_id = block.id

                logger.debug("Calling tool: %s(%s)", tool_name, json.dumps(tool_args)[:120])
                tool_calls_log.append({"tool": tool_name, "args": tool_args})

                # Run the actual tool function
                if tool_name in TOOL_REGISTRY:
                    try:
                        result = TOOL_REGISTRY[tool_name](**tool_args)
                        result_str = json.dumps(result, indent=2)
                    except Exception as exc:
                        logger.warning("Tool %s raised: %s", tool_name, exc)
                        result_str = json.dumps({"error": str(exc)})
                else:
                    result_str = json.dumps({"error": f"Unknown tool: {tool_name}"})

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_str,
                })

            # Feed all tool results back to Claude as a user message
            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop_reason — treat whatever text Claude produced as final
        logger.warning("Unexpected stop_reason=%s, returning as final.", response.stop_reason)
        final_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        return {
            "final_report": final_text or "Agent stopped unexpectedly.",
            "agent_steps": tool_calls_log,
            "iterations": iteration,
        }

    # Hit iteration limit
    logger.error("Agent hit max_iterations=%d without completing.", max_iterations)
    return {
        "final_report": (
            "⚠️ Agent reached the maximum iteration limit without completing the analysis. "
            "The log may be too complex or malformed."
        ),
        "agent_steps": tool_calls_log,
        "iterations": iteration,
    }


def analyze_rpa_logs(log_text: str) -> str:
    """Backward-compatible wrapper — returns only the final report text."""
    return run_agent(log_text)["final_report"]
