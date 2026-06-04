"""
Integration tests for the FastAPI endpoints.
The /analyze and /analyze/agent endpoints are mocked so no API key is needed.
The /incidents endpoints hit the real knowledge base file.
"""

import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

import os
# Set before app import so the auth middleware picks it up
os.environ["API_KEY"] = "test-key"

from app.main import app  # noqa: E402

client = TestClient(app, headers={"X-API-Key": "test-key"})

SAMPLE_LOG = b"""
2026-02-21 10:00:01 [Info] Execution Started. Process: SAP_Invoice_Processing.
2026-02-21 10:00:12 [Error] System.Exception: Cannot find the UI element.
2026-02-21 10:00:20 [Fatal] BusinessRuleException: Customer ID 'LL-987' not found.
2026-02-21 10:00:21 [Info] Execution Ended. Status: Failed.
""".strip()

MOCK_AGENT_RESULT = {
    "final_report": "🔍 ROOT CAUSE: Test root cause.\n🏷️ CLASSIFICATION: Business Exception.",
    "agent_steps": [{"tool": "classify_error", "args": {"log_text": "..."}}],
    "iterations": 2,
}


# ── GET / ─────────────────────────────────────────────────────────────────────
class TestRoot:
    def test_returns_200(self):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_response_contains_service_name(self):
        resp = client.get("/")
        assert "Incident Commander" in resp.json()["service"]

    def test_lists_endpoints(self):
        resp = client.get("/")
        assert "endpoints" in resp.json()


# ── POST /analyze/agent ───────────────────────────────────────────────────────
class TestAnalyzeAgent:
    def test_returns_200_with_valid_file(self):
        with patch("app.engine.run_agent", return_value=MOCK_AGENT_RESULT):
            resp = client.post(
                "/analyze/agent",
                files={"file": ("log.txt", SAMPLE_LOG, "text/plain")},
            )
        assert resp.status_code == 200

    def test_response_has_required_fields(self):
        with patch("app.engine.run_agent", return_value=MOCK_AGENT_RESULT):
            resp = client.post(
                "/analyze/agent",
                files={"file": ("log.txt", SAMPLE_LOG, "text/plain")},
            )
        data = resp.json()
        assert "final_report" in data
        assert "agent_steps" in data
        assert "iterations" in data

    def test_rejects_non_txt_file(self):
        resp = client.post(
            "/analyze/agent",
            files={"file": ("log.pdf", SAMPLE_LOG, "application/pdf")},
        )
        assert resp.status_code == 400

    def test_rejects_empty_file(self):
        resp = client.post(
            "/analyze/agent",
            files={"file": ("empty.txt", b"   ", "text/plain")},
        )
        assert resp.status_code == 400

    def test_missing_api_key_returns_503(self):
        with patch("app.engine.run_agent", side_effect=EnvironmentError("ANTHROPIC_API_KEY not set")):
            resp = client.post(
                "/analyze/agent",
                files={"file": ("log.txt", SAMPLE_LOG, "text/plain")},
            )
        assert resp.status_code == 503


# ── POST /analyze (v1 endpoint) ───────────────────────────────────────────────
class TestAnalyzeV1:
    def test_returns_200_with_valid_file(self):
        with patch("app.engine.analyze_rpa_logs", return_value="Test analysis result"):
            resp = client.post(
                "/analyze",
                files={"file": ("log.txt", SAMPLE_LOG, "text/plain")},
            )
        assert resp.status_code == 200

    def test_response_has_analysis_field(self):
        with patch("app.engine.analyze_rpa_logs", return_value="Test analysis result"):
            resp = client.post(
                "/analyze",
                files={"file": ("log.txt", SAMPLE_LOG, "text/plain")},
            )
        assert "analysis" in resp.json()

    def test_rejects_empty_file(self):
        resp = client.post(
            "/analyze",
            files={"file": ("log.txt", b"", "text/plain")},
        )
        assert resp.status_code == 400

    def test_rejects_non_txt_file(self):
        resp = client.post(
            "/analyze",
            files={"file": ("image.png", SAMPLE_LOG, "image/png")},
        )
        assert resp.status_code == 400


# ── GET /incidents ────────────────────────────────────────────────────────────
class TestListIncidents:
    def test_returns_200(self):
        resp = client.get("/incidents")
        assert resp.status_code == 200

    def test_returns_list(self):
        resp = client.get("/incidents")
        assert isinstance(resp.json(), list)

    def test_each_incident_has_required_fields(self):
        resp = client.get("/incidents")
        required = {"id", "error_type", "keywords", "root_cause", "fix", "resolution"}
        for incident in resp.json():
            assert required.issubset(set(incident.keys()))


# ── POST /incidents ───────────────────────────────────────────────────────────
class TestAddIncident:
    def test_add_and_verify(self):
        """Add a test incident and verify it appears in the list."""
        payload = {
            "error_type": "System Exception",
            "keywords": ["pytest", "test_keyword_unique_12345"],
            "root_cause": "Test root cause for pytest.",
            "fix": "Test fix.",
            "resolution": "Test resolution.",
        }
        # Add it
        resp = client.post("/incidents", json=payload)
        assert resp.status_code == 201
        created = resp.json()
        assert created["id"].startswith("INC-")
        assert created["error_type"] == "System Exception"

        # Verify it shows up in list
        list_resp = client.get("/incidents")
        ids = [i["id"] for i in list_resp.json()]
        assert created["id"] in ids

        # Clean up — remove the test incident so it doesn't pollute future runs
        import json
        from app.main import INCIDENTS_FILE
        incidents = json.loads(INCIDENTS_FILE.read_text())
        incidents = [i for i in incidents if i["id"] != created["id"]]
        INCIDENTS_FILE.write_text(json.dumps(incidents, indent=2))

    def test_rejects_missing_required_fields(self):
        resp = client.post("/incidents", json={"error_type": "System Exception"})
        assert resp.status_code == 422  # validation error
