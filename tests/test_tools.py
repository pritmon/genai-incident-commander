"""
Unit tests for app/tools.py — all 4 specialist tools.
These tests run fully offline with no API calls.
"""

import pytest
from app.tools import (
    classify_error,
    extract_keywords,
    search_past_incidents,
    suggest_selector_fix,
    TOOL_REGISTRY,
)

# ── Sample log fixture ─────────────────────────────────────────────────────────
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


# ── classify_error ─────────────────────────────────────────────────────────────
class TestClassifyError:
    def test_returns_dict_with_required_keys(self):
        result = classify_error(SAMPLE_LOG)
        assert "classification" in result
        assert "reason" in result

    def test_classification_is_string(self):
        result = classify_error(SAMPLE_LOG)
        assert isinstance(result["classification"], str)

    def test_business_exception_detected(self):
        log = "BusinessRuleException: Customer ID not found in database."
        result = classify_error(log)
        assert "Business" in result["classification"]

    def test_system_exception_detected(self):
        log = "System.Exception: Cannot find UI element. Selector timeout."
        result = classify_error(log)
        assert "System" in result["classification"]

    def test_empty_log_does_not_crash(self):
        result = classify_error("no errors here at all")
        assert isinstance(result["classification"], str)


# ── extract_keywords ──────────────────────────────────────────────────────────
class TestExtractKeywords:
    def test_returns_dict_with_required_keys(self):
        result = extract_keywords(SAMPLE_LOG)
        assert "keywords" in result
        assert "error_lines" in result

    def test_keywords_is_list(self):
        result = extract_keywords(SAMPLE_LOG)
        assert isinstance(result["keywords"], list)

    def test_finds_error_lines(self):
        result = extract_keywords(SAMPLE_LOG)
        # Should find the [Error], [Warn], [Fatal] lines
        assert len(result["error_lines"]) >= 2

    def test_error_lines_contain_error_markers(self):
        result = extract_keywords(SAMPLE_LOG)
        for line in result["error_lines"]:
            assert any(
                marker in line.lower()
                for marker in ["[error]", "[warn]", "[fatal]"]
            )

    def test_keywords_not_empty_for_real_log(self):
        result = extract_keywords(SAMPLE_LOG)
        assert len(result["keywords"]) > 0


# ── search_past_incidents ─────────────────────────────────────────────────────
class TestSearchPastIncidents:
    def test_returns_dict_with_required_keys(self):
        result = search_past_incidents(["BusinessRuleException", "Customer"], "Business Exception")
        assert "found" in result
        assert "similar_incidents" in result

    def test_finds_customer_id_incident(self):
        result = search_past_incidents(["BusinessRuleException", "Customer", "database"])
        assert result["found"] is True
        assert len(result["similar_incidents"]) > 0

    def test_finds_selector_incident(self):
        result = search_past_incidents(["btn_save", "selector", "UI element"], "System Exception")
        assert result["found"] is True

    def test_no_match_returns_found_false(self):
        result = search_past_incidents(["zzz_nonexistent_keyword_xyz"])
        assert result["found"] is False
        assert result["similar_incidents"] == []

    def test_empty_keywords_does_not_crash(self):
        result = search_past_incidents([])
        assert "found" in result

    def test_results_sorted_by_score(self):
        result = search_past_incidents(
            ["BusinessRuleException", "Customer", "database", "not found"],
            "Business Exception"
        )
        if result["found"] and len(result["similar_incidents"]) > 1:
            scores = [r["score"] for r in result["similar_incidents"]]
            assert scores == sorted(scores, reverse=True)

    def test_returns_max_two_results(self):
        result = search_past_incidents(
            ["Customer", "database", "timeout", "connection", "network"],
            "Business Exception"
        )
        assert len(result["similar_incidents"]) <= 2


# ── suggest_selector_fix ──────────────────────────────────────────────────────
class TestSuggestSelectorFix:
    def test_returns_dict_with_required_keys(self):
        result = suggest_selector_fix(SAMPLE_LOG)
        assert "found_selectors" in result

    def test_finds_sap_selector(self):
        result = suggest_selector_fix(SAMPLE_LOG)
        assert result["found_selectors"] is True

    def test_suggestion_has_original_and_fix(self):
        result = suggest_selector_fix(SAMPLE_LOG)
        assert len(result["suggestions"]) > 0
        suggestion = result["suggestions"][0]
        assert "original" in suggestion
        assert "suggested_fix" in suggestion
        assert "explanation" in suggestion

    def test_no_selector_in_log(self):
        log = "BusinessRuleException: Customer ID not found."
        result = suggest_selector_fix(log)
        assert result["found_selectors"] is False

    def test_hardened_selector_includes_title_and_parentid(self):
        result = suggest_selector_fix(SAMPLE_LOG)
        fix = result["suggestions"][0]["suggested_fix"]
        assert "title" in fix
        assert "parentid" in fix

    def test_btn_save_selector_identified(self):
        result = suggest_selector_fix(SAMPLE_LOG)
        originals = [s["original"] for s in result["suggestions"]]
        assert any("btn_save" in o for o in originals)


# ── TOOL_REGISTRY ─────────────────────────────────────────────────────────────
class TestToolRegistry:
    def test_all_tools_registered(self):
        expected = {"classify_error", "extract_keywords", "search_past_incidents", "suggest_selector_fix"}
        assert set(TOOL_REGISTRY.keys()) == expected

    def test_all_tools_are_callable(self):
        for name, fn in TOOL_REGISTRY.items():
            assert callable(fn), f"{name} is not callable"
