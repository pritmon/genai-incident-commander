"""
main.py — The front door of the project. Built with FastAPI.

WHAT THIS FILE DOES:
  - Receives log files from users over the internet
  - Validates the file (must be .txt, not empty)
  - Checks the API key (security)
  - Passes the log to Claude AI (engine.py)
  - Returns the analysis back to the user as JSON

ENDPOINTS (URLs you can call):
  GET  /                → health check, lists all endpoints
  POST /analyze/agent   → full agentic analysis (shows every tool Claude called)
  POST /analyze         → classic analysis (returns final report text only)
  POST /incidents       → add a new resolved incident to the knowledge base
  GET  /incidents       → list all past incidents in the knowledge base
"""

import json      # used to read/write past_incidents.json
import logging   # used to print logs to terminal
import os        # used to read environment variables
from pathlib import Path       # used to handle file paths cleanly
from typing import List, Optional  # used for type hints

# FastAPI imports
from fastapi import Depends, FastAPI, File, HTTPException, Security, UploadFile, status
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Our own files
from app import engine                        # Claude AI agentic loop
from app.tools import search_past_incidents   # tool for searching past incidents


# ──────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP
# Prints messages like: "2024-01-01 10:00:00 | INFO | Received log (500 chars)"
# LOG_LEVEL can be changed in .env → DEBUG shows more detail, WARNING shows less
# ──────────────────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# DATADOG SETUP
# Datadog monitors the API layer — request count, response time, error rate.
# Arize monitors the AI layer (Claude calls, tokens, cost).
# Together: full observability — infrastructure + LLM.
#
# Activates only if DD_API_KEY is set in .env
# If not set — app works normally, just without Datadog tracking
# ──────────────────────────────────────────────────────────────────────────────
def _setup_datadog():
    """Initialises Datadog if DD_API_KEY is set. Called once when module loads."""
    dd_api_key = os.getenv("DD_API_KEY")
    if not dd_api_key:
        logger.info("Datadog monitoring disabled — DD_API_KEY not set.")
        return
    try:
        from datadog import initialize
        initialize(
            api_key=dd_api_key,
            app_key=os.getenv("DD_APP_KEY", ""),
            host_name="genai-incident-commander",
        )
        logger.info("Datadog monitoring enabled ✅")
    except Exception as exc:
        logger.warning("Datadog setup failed: %s", exc)

_setup_datadog()


# ──────────────────────────────────────────────────────────────────────────────
# API KEY AUTHENTICATION
# Protects all endpoints — caller must send correct key in X-API-Key header
# If API_KEY is not set in .env → auth is disabled (useful for local development)
# ──────────────────────────────────────────────────────────────────────────────

# Read the expected API key from .env
_API_KEY = os.getenv("API_KEY")

# Tell FastAPI to look for X-API-Key in request headers
# auto_error=False means we handle the error ourselves (custom message)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str = Security(_api_key_header)):
    """
    Checks if the X-API-Key header matches the expected key.
    Called automatically on every protected endpoint.

    If API_KEY is not set in .env → skip auth (local dev mode)
    If wrong key → return 401 Unauthorized
    If correct key → allow request through
    """
    if not _API_KEY:
        return  # Auth disabled — no API_KEY set in .env

    if key != _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Pass it as X-API-Key header.",
        )


# ──────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE BASE FILE PATH
# Points to data/past_incidents.json — the file that stores past RPA failures
# ──────────────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"       # → project_root/data/
INCIDENTS_FILE = DATA_DIR / "past_incidents.json"      # → project_root/data/past_incidents.json


# ──────────────────────────────────────────────────────────────────────────────
# CREATE THE FASTAPI APP
# This one line creates the entire server + auto-generates Swagger UI at /docs
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="RPA Agentic Incident Commander",
    description=(
        "Claude-powered agentic log analyzer for RPA Ops teams. "
        "Classifies errors, searches past incidents, and suggests fixes "
        "using a multi-tool reasoning loop — not just one big prompt."
    ),
    version="2.0.0",
)

# ── Serve the beautiful UI ────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/ui", include_in_schema=False)
def serve_ui():
    """Serves the beautiful HTML UI at /ui"""
    return FileResponse(STATIC_DIR / "index.html")


# ──────────────────────────────────────────────────────────────────────────────
# DATA SCHEMAS (Pydantic Models)
# These define the exact shape of request and response data.
# FastAPI uses these to auto-validate data and generate Swagger documentation.
# ──────────────────────────────────────────────────────────────────────────────

class AgentStep(BaseModel):
    """Represents one tool call the agent made during analysis."""
    tool: str   # tool name e.g. "classify_error"
    args: dict  # arguments passed to the tool


class AgentAnalysisResponse(BaseModel):
    """Response shape for the /analyze/agent endpoint."""
    final_report: str          # the complete incident analysis
    agent_steps: List[AgentStep]  # every tool Claude called (in order)
    iterations: int            # how many loops Claude took


class AnalysisResponse(BaseModel):
    """Response shape for the classic /analyze endpoint (backward compatible)."""
    analysis: str  # just the final report text


class NewIncident(BaseModel):
    """Request shape for adding a new incident via POST /incidents."""
    error_type: str = Field(..., description="'Business Exception' or 'System Exception'")
    keywords: List[str] = Field(..., description="Key terms from the log")
    root_cause: str = Field(..., description="What caused the failure")
    fix: str = Field(..., description="How to fix it")
    resolution: str = Field(..., description="What was done to resolve it")


class IncidentResponse(BaseModel):
    """Response shape when returning a single incident."""
    id: str
    error_type: str
    keywords: List[str]
    root_cause: str
    fix: str
    resolution: str


# ──────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# Small reusable functions used by multiple endpoints
# ──────────────────────────────────────────────────────────────────────────────

def _read_file_or_error(file_content: bytes, filename: str) -> str:
    """
    Converts uploaded file bytes to a string.
    Returns 400 error if the file cannot be decoded (e.g. binary file).
    """
    try:
        return file_content.decode("utf-8")  # convert bytes → string
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not decode '{filename}'. Make sure it is a UTF-8 text file.",
        )


def _validate_log_file(file: UploadFile) -> None:
    """
    Checks that the uploaded file is a .txt file.
    Returns 400 error if it is a PDF, image, or other file type.
    """
    is_txt = file.filename.endswith(".txt") if file.filename else False
    is_plain = (file.content_type or "").startswith("text/plain")

    if not (is_txt or is_plain):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt files are supported.",
        )


def _load_incidents() -> list[dict]:
    """Reads and returns all incidents from past_incidents.json."""
    with open(INCIDENTS_FILE, "r") as f:
        return json.load(f)


def _save_incidents(incidents: list[dict]) -> None:
    """Saves the updated incidents list back to past_incidents.json."""
    with open(INCIDENTS_FILE, "w") as f:
        json.dump(incidents, f, indent=2)


# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS (Routes)
# Each function below handles one URL
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    """
    Health check endpoint.
    Returns a simple JSON showing the service is running and lists all endpoints.
    No authentication required — useful for checking if server is alive.
    """
    return {
        "service": "RPA Agentic Incident Commander v2.0 (Claude)",
        "endpoints": {
            "POST /analyze/agent": "Full agentic analysis — shows every tool Claude called",
            "POST /analyze":       "Classic analysis (backward-compatible)",
            "POST /incidents":     "Add a new resolved incident to the knowledge base",
            "GET  /incidents":     "List all past incidents",
            "GET  /docs":          "Swagger UI",
        },
    }


@app.post("/analyze/agent", response_model=AgentAnalysisResponse)
async def analyze_log_agentic(
    file: UploadFile = File(...),           # the uploaded .txt log file
    _: None = Depends(verify_api_key)       # checks X-API-Key header first
):
    """
    🤖 FULL AGENTIC ANALYSIS

    Sends the log to Claude AI.
    Claude calls tools step by step, loops until confident, writes report.

    Returns:
      - final_report  → the complete incident analysis
      - agent_steps   → every tool Claude called (transparent reasoning)
      - iterations    → how many loops Claude took
    """

    # Step 1: Check file type (must be .txt)
    _validate_log_file(file)

    # Step 2: Read the file content
    content = await file.read()

    # Step 3: Convert bytes to string
    log_text = _read_file_or_error(content, file.filename or "upload.txt")

    # Step 4: Reject empty files
    if not log_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    logger.info("Received log for agentic analysis (%d chars)", len(log_text))

    # Step 5: Run the Claude agentic loop
    import time
    start_time = time.time()
    try:
        result = engine.run_agent(log_text)

        # ── Send metrics to Datadog (if enabled) ─────────────────────────────
        try:
            from datadog import statsd
            elapsed = time.time() - start_time
            statsd.increment("incident_commander.analysis.success")        # count successful analyses
            statsd.histogram("incident_commander.analysis.duration", elapsed)  # response time
            statsd.increment("incident_commander.analysis.iterations",
                             value=result.get("iterations", 1))            # how many agent loops
        except Exception:
            pass  # Datadog is optional — never break the main flow
        # ─────────────────────────────────────────────────────────────────────

        return result  # FastAPI auto-converts dict to JSON response

    except EnvironmentError as exc:
        # ANTHROPIC_API_KEY is missing
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Agent error")
        try:
            from datadog import statsd
            statsd.increment("incident_commander.analysis.error")  # count errors
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {exc}",
        )


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_log_file(
    file: UploadFile = File(...),          # the uploaded .txt log file
    _: None = Depends(verify_api_key)      # checks X-API-Key header first
):
    """
    📄 CLASSIC ANALYSIS (Backward Compatible)

    Same as /analyze/agent but returns ONLY the final report text.
    Kept for older clients that used the v1 API.
    Internally still uses the full Claude agentic loop.
    """

    # Same validation steps as /analyze/agent
    _validate_log_file(file)
    content = await file.read()
    log_text = _read_file_or_error(content, file.filename or "upload.txt")

    if not log_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    logger.info("Received log for classic analysis (%d chars)", len(log_text))

    try:
        # analyze_rpa_logs() returns only the string (not the full dict)
        analysis_result = engine.analyze_rpa_logs(log_text)
        return {"analysis": analysis_result}

    except EnvironmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Analysis error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating analysis: {exc}",
        )


@app.post("/incidents", response_model=IncidentResponse, status_code=201)
def add_incident(
    incident: NewIncident,               # the new incident data (JSON body)
    _: None = Depends(verify_api_key)    # checks X-API-Key header first
):
    """
    ➕ ADD NEW INCIDENT TO KNOWLEDGE BASE

    After you resolve a real RPA failure, add it here.
    The agent will use it next time a similar failure occurs.
    This is how the agent gets smarter over time.

    Auto-generates the next ID (e.g. INC-005, INC-006...)
    """

    # Load all existing incidents
    incidents = _load_incidents()

    # Find the highest existing ID number and add 1
    existing_ids = [i.get("id", "INC-000") for i in incidents]
    max_num = max((int(i.split("-")[1]) for i in existing_ids if "-" in i), default=0)
    new_id = f"INC-{max_num + 1:03d}"  # e.g. INC-005

    # Build the new incident record
    new_record = {
        "id": new_id,
        "error_type": incident.error_type,
        "keywords": incident.keywords,
        "root_cause": incident.root_cause,
        "fix": incident.fix,
        "resolution": incident.resolution,
    }

    # Add to list and save back to file
    incidents.append(new_record)
    _save_incidents(incidents)

    logger.info("Added new incident %s (%s)", new_id, incident.error_type)
    return new_record  # returns 201 Created with the new incident


@app.get("/incidents", response_model=list[IncidentResponse])
def list_incidents(
    _: None = Depends(verify_api_key)  # checks X-API-Key header first
) -> List[dict]:
    """
    📋 LIST ALL PAST INCIDENTS

    Returns every incident stored in past_incidents.json.
    Useful for reviewing the knowledge base or debugging why
    the agent matched (or didn't match) a certain past incident.
    """
    return _load_incidents()
