"""
tools.py — All the tools the AI agent can call.
Each function does one specific job, like a specialist doctor.
"""

import json
import os


# ── 1. CLASSIFY ERROR ──────────────────────────────────────────────────────────
def classify_error(log_text: str) -> dict:
    """
    Quick keyword-based pre-classification of the log.
    The agent uses this as a first signal before going deeper.
    """
    log_lower = log_text.lower()

    business_signals = [
        "businessruleexception", "business exception", "customer id", "not found in database",
        "invalid data", "duplicate", "validation failed", "missing field"
    ]
    system_signals = [
        "system.exception", "ui element", "selector", "timeout", "connection",
        "network", "crashed", "unhandled", "null reference", "index out of range"
    ]

    biz_score = sum(1 for s in business_signals if s in log_lower)
    sys_score = sum(1 for s in system_signals if s in log_lower)

    if biz_score > sys_score:
        classification = "Business Exception"
        reason = f"Found {biz_score} business-related signals in the log."
    elif sys_score > biz_score:
        classification = "System Exception"
        reason = f"Found {sys_score} system-related signals in the log."
    else:
        classification = "Ambiguous — needs deeper analysis"
        reason = "Equal signals for both types. Agent should investigate further."

    return {"classification": classification, "reason": reason}


# ── 2. EXTRACT ROOT CAUSE KEYWORDS ────────────────────────────────────────────
def extract_keywords(log_text: str) -> dict:
    """
    Pulls out the most important error keywords from the log
    so the agent can search past incidents intelligently.
    """
    important_terms = []
    lines = log_text.splitlines()

    for line in lines:
        line_lower = line.lower()
        # Focus on error/fatal/warn lines — that's where the real info is
        if any(level in line_lower for level in ["[error]", "[fatal]", "[warn]"]):
            # Extract words that look like identifiers, exceptions, or SAP terms
            for word in line.split():
                cleaned = word.strip("[]().,:'\"")
                if len(cleaned) > 4 and (
                    cleaned[0].isupper() or
                    "Exception" in cleaned or
                    "sap" in cleaned.lower() or
                    cleaned.startswith("btn_") or
                    cleaned.startswith("id=")
                ):
                    important_terms.append(cleaned)

    return {
        "keywords": list(set(important_terms)),
        "error_lines": [l for l in lines if any(x in l.lower() for x in ["[error]", "[fatal]", "[warn]"])]
    }


# ── 3. SEARCH PAST INCIDENTS ──────────────────────────────────────────────────
def search_past_incidents(keywords: list[str], error_type: str = "") -> dict:
    """
    Searches our local incident knowledge base (past_incidents.json)
    to find similar past failures and their resolutions.
    This is the RAG part — retrieving relevant past knowledge.
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, "data", "past_incidents.json")

    with open(db_path, "r") as f:
        incidents = json.load(f)

    keywords_lower = [k.lower() for k in keywords]
    matches = []

    for incident in incidents:
        incident_keywords = [k.lower() for k in incident["keywords"]]
        overlap = set(keywords_lower) & set(incident_keywords)

        # Also match on error type if provided
        type_match = error_type.lower() in incident["error_type"].lower() if error_type else False

        score = len(overlap) + (2 if type_match else 0)  # type match is worth 2 points

        if score > 0:
            matches.append({
                "incident_id": incident["id"],
                "score": score,
                "error_type": incident["error_type"],
                "root_cause": incident["root_cause"],
                "fix": incident["fix"],
                "resolution": incident["resolution"]
            })

    # Sort by relevance score
    matches.sort(key=lambda x: x["score"], reverse=True)
    top_matches = matches[:2]  # Return top 2 most relevant

    if top_matches:
        return {"found": True, "similar_incidents": top_matches}
    else:
        return {"found": False, "similar_incidents": [], "message": "No similar past incidents found."}


# ── 4. SUGGEST SAP SELECTOR FIX ───────────────────────────────────────────────
def suggest_selector_fix(log_text: str) -> dict:
    """
    Scans the log for broken SAP UI selectors and suggests
    a hardened version with additional attributes for stability.
    """
    import re

    # Find SAP selector patterns like <sap id='...' />
    selector_pattern = r"<sap[^>]+/>"
    found_selectors = re.findall(selector_pattern, log_text)

    if not found_selectors:
        return {"found_selectors": False, "message": "No SAP selectors found in the log."}

    suggestions = []
    for selector in found_selectors:
        # Extract the id attribute
        id_match = re.search(r"id='([^']+)'", selector)
        element_id = id_match.group(1) if id_match else "unknown"

        # Suggest a hardened version
        suggestion = {
            "original": selector,
            "issue": "Selector is too brittle — relies only on id which can change dynamically.",
            "suggested_fix": f"<sap id='{element_id}' title='{element_id.replace('btn_', '').replace('_', ' ').title()}' parentid='toolbar' />",
            "explanation": "Adding 'title' and 'parentid' makes the selector resilient to SAP UI changes."
        }
        suggestions.append(suggestion)

    return {"found_selectors": True, "suggestions": suggestions}


# ── TOOL REGISTRY — maps tool names to actual functions ───────────────────────
TOOL_REGISTRY = {
    "classify_error": classify_error,
    "extract_keywords": extract_keywords,
    "search_past_incidents": search_past_incidents,
    "suggest_selector_fix": suggest_selector_fix,
}
