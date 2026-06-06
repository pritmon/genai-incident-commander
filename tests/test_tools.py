"""
test_tools.py — Tests for all 4 specialist tools in app/tools.py

WHAT IS TESTED HERE:
  - classify_error       → does it correctly identify Business vs System exceptions?
  - extract_keywords     → does it pull out the right words from error lines?
  - search_past_incidents → does it find the right past incidents by keyword?
  - suggest_selector_fix  → does it detect and fix broken SAP selectors?
  - TOOL_REGISTRY        → are all 4 tools properly registered?

HOW TO RUN:
  pytest tests/test_tools.py -v

NOTE: These tests run fully OFFLINE — no Claude API key needed.
      They only test the Python tool functions directly.
"""

import pytest
from app.tools import (
    classify_error,
    extract_keywords,
    search_past_incidents,
    suggest_selector_fix,
    TOOL_REGISTRY,
)

# ──────────────────────────────────────────────────────────────────────────────
# SAMPLE LOG — used across all tests
# This is a realistic RPA log with both a System and Business exception
# ──────────────────────────────────────────────────────────────────────────────
SAMPLE_LOG = """
2026-02-21 10:00:01 [Info] Execution Started. Process: SAP_Invoice_Processing.
2026-02-21 10:00:05 [Info] Navigating to SAP Transaction VA01.
2026-02-21 10:00:12 [Error] System.Exception: Cannot find the UI element corresponding to the selector: <sap id='btn_save' />.
    at Source: Click Save (REFramework State: Process Transaction)
2026-02-21 10:00:13 [Warn] Retrying Transaction 1...
2026-02-21 10:00:20 [Fatal] BusinessRuleException: Customer ID 'LL-987' not found in database.
    at Source: Validate Data (REFramework State: Get Transaction Data)
2026-02-21 10:00:21 [Info] Execution Ended. Status: Failed.
""".strip()


# ──────────────────────────────────────────────────────────────────────────────
# TESTS FOR classify_error
# ──────────────────────────────────────────────────────────────────────────────
class TestClassifyError:

    def test_returns_dict_with_required_keys(self):
        """Result must always have 'classification' and 'reason' keys."""
        result = classify_error(SAMPLE_LOG)
        assert "classification" in result
        assert "reason" in result

    def test_classification_is_string(self):
        """Classification value must be a string."""
        result = classify_error(SAMPLE_LOG)
        assert isinstance(result["classification"], str)

    def test_business_exception_detected(self):
        """Log with 'BusinessRuleException' and 'not found in database' → Business Exception."""
        log = "BusinessRuleException: Customer ID not found in database."
        result = classify_error(log)
        assert "Business" in result["classification"]

    def test_system_exception_detected(self):
        """Log with 'System.Exception', 'UI element', 'selector', 'timeout' → System Exception."""
        log = "System.Exception: Cannot find UI element. Selector timeout."
        result = classify_error(log)
        assert "System" in result["classification"]

    def test_empty_log_does_not_crash(self):
        """Even a log with no error keywords should return a valid string, not crash."""
        result = classify_error("no errors here at all")
        assert isinstance(result["classification"], str)


# ──────────────────────────────────────────────────────────────────────────────
# TESTS FOR extract_keywords
# ──────────────────────────────────────────────────────────────────────────────
class TestExtractKeywords:

    def test_returns_dict_with_required_keys(self):
        """Result must always have 'keywords' and 'error_lines' keys."""
        result = extract_keywords(SAMPLE_LOG)
        assert "keywords" in result
        assert "error_lines" in result

    def test_keywords_is_list(self):
        """Keywords must be returned as a list."""
        result = extract_keywords(SAMPLE_LOG)
        assert isinstance(result["keywords"], list)

    def test_finds_error_lines(self):
        """Must find at least 2 error/fatal/warn lines in the sample log."""
        result = extract_keywords(SAMPLE_LOG)
        assert len(result["error_lines"]) >= 2

    def test_error_lines_contain_error_markers(self):
        """Every line in error_lines must contain [Error], [Warn], or [Fatal]."""
        result = extract_keywords(SAMPLE_LOG)
        for line in result["error_lines"]:
            assert any(
                marker in line.lower()
                for marker in ["[error]", "[warn]", "[fatal]"]
            )

    def test_keywords_not_empty_for_real_log(self):
        """A real log with errors should produce at least 1 keyword."""
        result = extract_keywords(SAMPLE_LOG)
        assert len(result["keywords"]) > 0


# ──────────────────────────────────────────────────────────────────────────────
# TESTS FOR search_past_incidents
# ──────────────────────────────────────────────────────────────────────────────
class TestSearchPastIncidents:

    def test_returns_dict_with_required_keys(self):
        """Result must always have 'found' and 'similar_incidents' keys."""
        result = search_past_incidents(["BusinessRuleException", "Customer"], "Business Exception")
        assert "found" in result
        assert "similar_incidents" in result

    def test_finds_customer_id_incident(self):
        """Searching with customer-related keywords should find INC-002."""
        result = search_past_incidents(["BusinessRuleException", "Customer", "database"])
        assert result["found"] is True
        assert len(result["similar_incidents"]) > 0

    def test_finds_selector_incident(self):
        """Searching with selector keywords should find INC-001."""
        result = search_past_incidents(["btn_save", "selector", "UI element"], "System Exception")
        assert result["found"] is True

    def test_no_match_returns_found_false(self):
        """Searching with a made-up keyword should return found=False."""
        result = search_past_incidents(["zzz_nonexistent_keyword_xyz"])
        assert result["found"] is False
        assert result["similar_incidents"] == []

    def test_empty_keywords_does_not_crash(self):
        """Empty keyword list should not crash — just return found=False."""
        result = search_past_incidents([])
        assert "found" in result

    def test_results_sorted_by_score(self):
        """Results must be sorted by score — highest relevance first."""
        result = search_past_incidents(
            ["BusinessRuleException", "Customer", "database", "not found"],
            "Business Exception"
        )
        if result["found"] and len(result["similar_incidents"]) > 1:
            scores = [r["score"] for r in result["similar_incidents"]]
            assert scores == sorted(scores, reverse=True)

    def test_returns_max_two_results(self):
        """Should never return more than 2 results (top 2 only)."""
        result = search_past_incidents(
            ["Customer", "database", "timeout", "connection", "network"],
            "Business Exception"
        )
        assert len(result["similar_incidents"]) <= 2


# ──────────────────────────────────────────────────────────────────────────────
# TESTS FOR suggest_selector_fix
# ──────────────────────────────────────────────────────────────────────────────
class TestSuggestSelectorFix:

    def test_returns_dict_with_required_keys(self):
        """Result must always have 'found_selectors' key."""
        result = suggest_selector_fix(SAMPLE_LOG)
        assert "found_selectors" in result

    def test_finds_sap_selector(self):
        """Sample log contains <sap id='btn_save' /> — must be detected."""
        result = suggest_selector_fix(SAMPLE_LOG)
        assert result["found_selectors"] is True

    def test_suggestion_has_original_and_fix(self):
        """Each suggestion must have 'original', 'suggested_fix', and 'explanation'."""
        result = suggest_selector_fix(SAMPLE_LOG)
        assert len(result["suggestions"]) > 0
        suggestion = result["suggestions"][0]
        assert "original" in suggestion
        assert "suggested_fix" in suggestion
        assert "explanation" in suggestion

    def test_no_selector_in_log(self):
        """A log with no SAP selectors should return found_selectors=False."""
        log = "BusinessRuleException: Customer ID not found."
        result = suggest_selector_fix(log)
        assert result["found_selectors"] is False

    def test_hardened_selector_includes_title_and_parentid(self):
        """The fixed selector must include 'title' and 'parentid' attributes."""
        result = suggest_selector_fix(SAMPLE_LOG)
        fix = result["suggestions"][0]["suggested_fix"]
        assert "title" in fix
        assert "parentid" in fix

    def test_btn_save_selector_identified(self):
        """The original broken selector <sap id='btn_save' /> must be found."""
        result = suggest_selector_fix(SAMPLE_LOG)
        originals = [s["original"] for s in result["suggestions"]]
        assert any("btn_save" in o for o in originals)


# ──────────────────────────────────────────────────────────────────────────────
# TESTS FOR TOOL_REGISTRY
# ──────────────────────────────────────────────────────────────────────────────
class TestToolRegistry:

    def test_all_tools_registered(self):
        """TOOL_REGISTRY must contain exactly these 4 tools — no more, no less."""
        expected = {
            "classify_error",
            "extract_keywords",
            "search_past_incidents",
            "suggest_selector_fix"
        }
        assert set(TOOL_REGISTRY.keys()) == expected

    def test_all_tools_are_callable(self):
        """Every value in TOOL_REGISTRY must be a callable function."""
        for name, fn in TOOL_REGISTRY.items():
            assert callable(fn), f"{name} is not callable"
