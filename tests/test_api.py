"""
test_api.py — Tests for all FastAPI endpoints in app/main.py

WHAT IS TESTED HERE:
  GET  /               → health check returns 200
  POST /analyze/agent  → agentic endpoint works, rejects bad files
  POST /analyze        → classic endpoint works, rejects bad files
  GET  /incidents      → returns list of incidents
  POST /incidents      → adds new incident, validates required fields

HOW TO RUN:
  pytest tests/test_api.py -v

IMPORTANT NOTES:
  - Claude AI is MOCKED — these tests don't make real API calls
  - No ANTHROPIC_API_KEY needed to run these tests
  - The /incidents tests DO read/write the real past_incidents.json file
    (any test-created incidents are cleaned up at the end)
"""

import json
import pytest
from fastapi.testclient import TestClient  # lets us make fake HTTP requests in tests
from unittest.mock import patch           # lets us replace real functions with fake ones

import os

# Set the API key BEFORE importing the app
# (the app reads API_KEY at import time, so it must be set first)
os.environ["API_KEY"] = "test-key"

from app.main import app  # noqa: E402 — import after setting env var

# Create a test client that automatically includes the API key header
# This simulates a real caller who has the correct key
client = TestClient(app, headers={"X-API-Key": "test-key"})

# ──────────────────────────────────────────────────────────────────────────────
# SAMPLE TEST DATA
# ──────────────────────────────────────────────────────────────────────────────

# A realistic RPA log used for file upload tests
SAMPLE_LOG = b"""
2026-02-21 10:00:01 [Info] Execution Started. Process: SAP_Invoice_Processing.
2026-02-21 10:00:12 [Error] System.Exception: Cannot find the UI element.
2026-02-21 10:00:20 [Fatal] BusinessRuleException: Customer ID 'LL-987' not found.
2026-02-21 10:00:21 [Info] Execution Ended. Status: Failed.
""".strip()

# Fake Claude AI response — used to mock engine.run_agent()
# This way tests pass even without a real Anthropic API key
MOCK_AGENT_RESULT = {
    "final_report": "🔍 ROOT CAUSE: Test root cause.\n🏷️ CLASSIFICATION: Business Exception.",
    "agent_steps": [{"tool": "classify_error", "args": {"log_text": "..."}}],
    "iterations": 2,
}


# ──────────────────────────────────────────────────────────────────────────────
# TESTS FOR GET /
# ──────────────────────────────────────────────────────────────────────────────
class TestRoot:

    def test_returns_200(self):
        """Health check must always return 200 OK."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_response_contains_service_name(self):
        """Response must mention 'Incident Commander' in the service field."""
        resp = client.get("/")
        assert "Incident Commander" in resp.json()["service"]

    def test_lists_endpoints(self):
        """Response must include an 'endpoints' section listing all routes."""
        resp = client.get("/")
        assert "endpoints" in resp.json()


# ──────────────────────────────────────────────────────────────────────────────
# TESTS FOR POST /analyze/agent
# ──────────────────────────────────────────────────────────────────────────────
class TestAnalyzeAgent:

    def test_returns_200_with_valid_file(self):
        """A valid .txt file with content should return 200 OK."""
        # Replace real Claude call with our fake MOCK_AGENT_RESULT
        with patch("app.engine.run_agent", return_value=MOCK_AGENT_RESULT):
            resp = client.post(
                "/analyze/agent",
                files={"file": ("log.txt", SAMPLE_LOG, "text/plain")},
            )
        assert resp.status_code == 200

    def test_response_has_required_fields(self):
        """Response must contain final_report, agent_steps, and iterations."""
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
        """Uploading a PDF should return 400 Bad Request."""
        resp = client.post(
            "/analyze/agent",
            files={"file": ("log.pdf", SAMPLE_LOG, "application/pdf")},
        )
        assert resp.status_code == 400

    def test_rejects_empty_file(self):
        """Uploading a blank/whitespace file should return 400 Bad Request."""
        resp = client.post(
            "/analyze/agent",
            files={"file": ("empty.txt", b"   ", "text/plain")},
        )
        assert resp.status_code == 400

    def test_missing_api_key_returns_503(self):
        """If ANTHROPIC_API_KEY is missing, should return 503 Service Unavailable."""
        with patch("app.engine.run_agent", side_effect=EnvironmentError("ANTHROPIC_API_KEY not set")):
            resp = client.post(
                "/analyze/agent",
                files={"file": ("log.txt", SAMPLE_LOG, "text/plain")},
            )
        assert resp.status_code == 503


# ──────────────────────────────────────────────────────────────────────────────
# TESTS FOR POST /analyze (classic v1 endpoint)
# ──────────────────────────────────────────────────────────────────────────────
class TestAnalyzeV1:

    def test_returns_200_with_valid_file(self):
        """A valid .txt file should return 200 OK."""
        with patch("app.engine.analyze_rpa_logs", return_value="Test analysis result"):
            resp = client.post(
                "/analyze",
                files={"file": ("log.txt", SAMPLE_LOG, "text/plain")},
            )
        assert resp.status_code == 200

    def test_response_has_analysis_field(self):
        """Response must contain an 'analysis' field with the report text."""
        with patch("app.engine.analyze_rpa_logs", return_value="Test analysis result"):
            resp = client.post(
                "/analyze",
                files={"file": ("log.txt", SAMPLE_LOG, "text/plain")},
            )
        assert "analysis" in resp.json()

    def test_rejects_empty_file(self):
        """Empty file should return 400 Bad Request."""
        resp = client.post(
            "/analyze",
            files={"file": ("log.txt", b"", "text/plain")},
        )
        assert resp.status_code == 400

    def test_rejects_non_txt_file(self):
        """Image file should return 400 Bad Request."""
        resp = client.post(
            "/analyze",
            files={"file": ("image.png", SAMPLE_LOG, "image/png")},
        )
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# TESTS FOR GET /incidents
# ──────────────────────────────────────────────────────────────────────────────
class TestListIncidents:

    def test_returns_200(self):
        """Listing incidents should always return 200 OK."""
        resp = client.get("/incidents")
        assert resp.status_code == 200

    def test_returns_list(self):
        """Response must be a JSON array (list)."""
        resp = client.get("/incidents")
        assert isinstance(resp.json(), list)

    def test_each_incident_has_required_fields(self):
        """Every incident in the list must have all 6 required fields."""
        resp = client.get("/incidents")
        required = {"id", "error_type", "keywords", "root_cause", "fix", "resolution"}
        for incident in resp.json():
            assert required.issubset(set(incident.keys()))


# ──────────────────────────────────────────────────────────────────────────────
# TESTS FOR POST /incidents
# ──────────────────────────────────────────────────────────────────────────────
class TestAddIncident:

    def test_add_and_verify(self):
        """
        Full round-trip test:
          1. Add a new incident via POST /incidents
          2. Verify it appears in GET /incidents list
          3. Clean it up so it doesn't pollute the real knowledge base
        """
        payload = {
            "error_type": "System Exception",
            "keywords": ["pytest", "test_keyword_unique_12345"],
            "root_cause": "Test root cause for pytest.",
            "fix": "Test fix.",
            "resolution": "Test resolution.",
        }

        # Step 1: Add the new incident
        resp = client.post("/incidents", json=payload)
        assert resp.status_code == 201           # 201 = Created

        created = resp.json()
        assert created["id"].startswith("INC-")  # ID must follow INC-XXX format
        assert created["error_type"] == "System Exception"

        # Step 2: Verify it shows up in the list
        list_resp = client.get("/incidents")
        ids = [i["id"] for i in list_resp.json()]
        assert created["id"] in ids

        # Step 3: Clean up — remove the test incident from the file
        # (so future test runs don't accumulate test data)
        from app.main import INCIDENTS_FILE
        incidents = json.loads(INCIDENTS_FILE.read_text())
        incidents = [i for i in incidents if i["id"] != created["id"]]
        INCIDENTS_FILE.write_text(json.dumps(incidents, indent=2))

    def test_rejects_missing_required_fields(self):
        """Sending incomplete data should return 422 Unprocessable Entity."""
        # Only sending error_type, missing keywords, root_cause, fix, resolution
        resp = client.post("/incidents", json={"error_type": "System Exception"})
        assert resp.status_code == 422  # 422 = validation error from Pydantic
