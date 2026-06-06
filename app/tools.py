"""
tools.py — The 4 specialist tools that Claude AI can call during analysis.

Think of these like specialist doctors in a hospital:
  - Tool 1: classify_error       → "What TYPE of problem is this?"
  - Tool 2: extract_keywords     → "What are the KEY WORDS in this error?"
  - Tool 3: search_past_incidents → "Have we seen this problem BEFORE?"
  - Tool 4: suggest_selector_fix  → "What is the EXACT FIX for the broken button?"

Claude AI decides WHICH tool to call and WHEN. We just provide the tools.
"""

import json  # used to read the past_incidents.json file
import os    # used to find the file path of past_incidents.json


# ──────────────────────────────────────────────────────────────────────────────
# TOOL 1 — CLASSIFY ERROR
# Question it answers: "Is this a Business problem or a System/Technical problem?"
# ──────────────────────────────────────────────────────────────────────────────
def classify_error(log_text: str) -> dict:
    """
    Reads the log and decides if the error is:
      - Business Exception → wrong data, missing customer, duplicate invoice
      - System Exception   → broken button, network timeout, UI element not found

    How it works:
      - Checks if "businessruleexception", "customer id" etc are in the log → Business
      - Checks if "system.exception", "selector", "timeout" etc are in log → System
      - Counts the matches and whichever has more wins
    """

    # Convert entire log to lowercase so "BusinessRuleException" matches "businessruleexception"
    log_lower = log_text.lower()

    # These words in the log = likely a Business Exception (data/rule problem)
    business_signals = [
        "businessruleexception",   # direct exception name
        "business exception",      # explicit mention
        "customer id",             # customer data issue
        "not found in database",   # missing record
        "invalid data",            # bad data
        "duplicate",               # duplicate entry
        "validation failed",       # data validation failed
        "missing field"            # required field not filled
    ]

    # These words in the log = likely a System Exception (technical/UI problem)
    system_signals = [
        "system.exception",        # direct exception name
        "ui element",              # UI element not found
        "selector",                # broken SAP selector
        "timeout",                 # connection timed out
        "connection",              # network issue
        "network",                 # network issue
        "crashed",                 # application crashed
        "unhandled",               # unhandled exception
        "null reference",          # code error
        "index out of range"       # code error
    ]

    # Count how many business keywords appear in the log
    biz_score = sum(1 for s in business_signals if s in log_lower)

    # Count how many system keywords appear in the log
    sys_score = sum(1 for s in system_signals if s in log_lower)

    # Whichever score is higher = that's the classification
    if biz_score > sys_score:
        classification = "Business Exception"
        reason = f"Found {biz_score} business-related signals in the log."
    elif sys_score > biz_score:
        classification = "System Exception"
        reason = f"Found {sys_score} system-related signals in the log."
    else:
        # Equal score = cannot decide, Claude will investigate further
        classification = "Ambiguous — needs deeper analysis"
        reason = "Equal signals for both types. Agent should investigate further."

    # Return result as a dictionary
    return {"classification": classification, "reason": reason}


# ──────────────────────────────────────────────────────────────────────────────
# TOOL 2 — EXTRACT KEYWORDS
# Question it answers: "What are the important words/terms from this error?"
# These keywords are later used to search past incidents
# ──────────────────────────────────────────────────────────────────────────────
def extract_keywords(log_text: str) -> dict:
    """
    Scans the log and pulls out the most important words.

    Strategy:
      - Only look at ERROR, FATAL, WARN lines (ignore INFO lines — not useful)
      - From those lines, extract words that look like:
          → Exception names (start with Capital letter)
          → SAP terms (contain 'sap')
          → Button names (start with 'btn_')
          → ID attributes (start with 'id=')
    """

    important_terms = []          # list to collect keywords
    lines = log_text.splitlines() # split log into individual lines

    for line in lines:
        line_lower = line.lower()

        # Only process lines that contain [Error], [Fatal], or [Warn]
        # Skip [Info] lines — they don't contain error details
        if any(level in line_lower for level in ["[error]", "[fatal]", "[warn]"]):

            # Loop through every word in this error line
            for word in line.split():

                # Clean up punctuation from word edges: remove [ ] ( ) . , : ' "
                cleaned = word.strip("[]().,:'\"")

                # Only keep the word if it is longer than 4 characters AND
                # looks like an important identifier
                if len(cleaned) > 4 and (
                    cleaned[0].isupper() or           # Capitalized = Exception name
                    "Exception" in cleaned or          # Contains word "Exception"
                    "sap" in cleaned.lower() or        # SAP related term
                    cleaned.startswith("btn_") or      # Button selector e.g. btn_save
                    cleaned.startswith("id=")          # ID attribute
                ):
                    important_terms.append(cleaned)

    return {
        # Remove duplicates using set(), then convert back to list
        "keywords": list(set(important_terms)),

        # Also return the actual error lines for reference
        "error_lines": [
            l for l in lines
            if any(x in l.lower() for x in ["[error]", "[fatal]", "[warn]"])
        ]
    }


# ──────────────────────────────────────────────────────────────────────────────
# TOOL 3 — SEARCH PAST INCIDENTS
# Question it answers: "Have we seen this exact problem before? What fixed it?"
# Searches the past_incidents.json knowledge base
# ──────────────────────────────────────────────────────────────────────────────
def search_past_incidents(keywords: list[str], error_type: str = "") -> dict:
    """
    Opens past_incidents.json and finds incidents similar to the current log.

    Matching logic:
      - Compare keywords from current log against keywords of each past incident
      - Count how many keywords overlap (match)
      - Each keyword match = 1 point
      - If error type also matches = 2 bonus points
      - Sort by score, return top 2 matches
    """

    # Find the path to past_incidents.json
    # __file__ = this file (tools.py) → go up 2 levels to reach project root
    base_dir = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, "data", "past_incidents.json")

    # Open and read the JSON file
    with open(db_path, "r") as f:
        incidents = json.load(f)  # loads list of past incident dictionaries

    # Convert all incoming keywords to lowercase for fair comparison
    keywords_lower = [k.lower() for k in keywords]

    matches = []  # will hold incidents that have at least 1 keyword match

    # Loop through every past incident in the knowledge base
    for incident in incidents:

        # Get this incident's keywords (also lowercase)
        incident_keywords = [k.lower() for k in incident["keywords"]]

        # Find common keywords between current log and this past incident
        # set() & set() = intersection = words that appear in BOTH sets
        overlap = set(keywords_lower) & set(incident_keywords)

        # Check if error type also matches (gives 2 bonus points)
        type_match = error_type.lower() in incident["error_type"].lower() if error_type else False

        # Calculate relevance score
        score = len(overlap) + (2 if type_match else 0)

        # Only include incidents that matched at least 1 keyword
        if score > 0:
            matches.append({
                "incident_id": incident["id"],
                "score": score,               # higher = more similar
                "error_type": incident["error_type"],
                "root_cause": incident["root_cause"],
                "fix": incident["fix"],
                "resolution": incident["resolution"]
            })

    # Sort by score — highest score first (most relevant at top)
    matches.sort(key=lambda x: x["score"], reverse=True)

    # Return only top 2 most relevant matches
    top_matches = matches[:2]

    if top_matches:
        return {"found": True, "similar_incidents": top_matches}
    else:
        return {
            "found": False,
            "similar_incidents": [],
            "message": "No similar past incidents found."
        }


# ──────────────────────────────────────────────────────────────────────────────
# TOOL 4 — SUGGEST SAP SELECTOR FIX
# Question it answers: "What is the correct fixed version of the broken SAP button?"
# ──────────────────────────────────────────────────────────────────────────────
def suggest_selector_fix(log_text: str) -> dict:
    """
    Looks for broken SAP UI selectors in the log and suggests a hardened version.

    Problem: SAP selectors like <sap id='btn_save' /> break after SAP upgrades
             because the ID changes dynamically.

    Solution: Add 'title' and 'parentid' to the selector so it still works
              even when the ID changes.

    Example:
      BROKEN:  <sap id='btn_save' />
      FIXED:   <sap id='btn_save' title='Save' parentid='toolbar' />
    """

    import re  # regex library — used to find patterns in text

    # Pattern to find SAP selectors: anything that looks like <sap ... />
    selector_pattern = r"<sap[^>]+/>"

    # Find all SAP selectors in the log
    found_selectors = re.findall(selector_pattern, log_text)

    # If no selectors found, return early
    if not found_selectors:
        return {
            "found_selectors": False,
            "message": "No SAP selectors found in the log."
        }

    suggestions = []

    # For each broken selector found, create a hardened replacement
    for selector in found_selectors:

        # Extract the id value from the selector e.g. btn_save
        id_match = re.search(r"id='([^']+)'", selector)
        element_id = id_match.group(1) if id_match else "unknown"

        # Build the fixed selector with extra attributes
        suggestion = {
            "original": selector,   # the broken version from the log

            "issue": "Selector is too brittle — relies only on id which can change dynamically.",

            # Fixed version: add title and parentid for stability
            "suggested_fix": (
                f"<sap id='{element_id}' "
                f"title='{element_id.replace('btn_', '').replace('_', ' ').title()}' "
                f"parentid='toolbar' />"
            ),

            "explanation": "Adding 'title' and 'parentid' makes the selector resilient to SAP UI changes."
        }
        suggestions.append(suggestion)

    return {"found_selectors": True, "suggestions": suggestions}


# ──────────────────────────────────────────────────────────────────────────────
# TOOL REGISTRY
# A dictionary that maps tool names (strings) to the actual functions above.
# Claude AI calls a tool by NAME (e.g. "classify_error").
# engine.py uses this registry to find and run the matching Python function.
# ──────────────────────────────────────────────────────────────────────────────
TOOL_REGISTRY = {
    "classify_error": classify_error,
    "extract_keywords": extract_keywords,
    "search_past_incidents": search_past_incidents,
    "suggest_selector_fix": suggest_selector_fix,
}
