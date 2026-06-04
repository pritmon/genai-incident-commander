"""
main.py — FastAPI application for the RPA Agentic Incident Commander.

Endpoints:
  GET  /                  → health check
  POST /analyze/agent     → full agentic analysis (returns tool steps + report)
  POST /analyze           → classic endpoint (backward-compatible, returns text only)
  POST /incidents         → add a new resolved incident to the knowledge base
  GET  /incidents         → list all past incidents
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Security, UploadFile, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field

from app import engine
from app.tools import search_past_incidents

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── API Key Auth ──────────────────────────────────────────────────────────────
_API_KEY = os.getenv("API_KEY")  # If not set, auth is disabled (local dev)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str = Security(_api_key_header)):
    """Validate X-API-Key header. Skipped if API_KEY env var is not set."""
    if not _API_KEY:
        return  # Auth disabled — local dev mode
    if key != _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Pass it as X-API-Key header.",
        )


# ── Knowledge base path ───────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
INCIDENTS_FILE = DATA_DIR / "past_incidents.json"

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="RPA Agentic Incident Commander",
    description=(
        "Claude-powered agentic log analyzer for RPA Ops teams. "
        "Classifies errors, searches past incidents, and suggests fixes "
        "using a multi-tool reasoning loop — not just one big prompt."
    ),
    version="2.0.0",
)


# ── Schemas ───────────────────────────────────────────────────────────────────
class AgentStep(BaseModel):
    tool: str
    args: dict


class AgentAnalysisResponse(BaseModel):
    final_report: str
    agent_steps: List[AgentStep]
    iterations: int


class AnalysisResponse(BaseModel):
    """Simple response for backward-compatible /analyze endpoint."""
    analysis: str


class NewIncident(BaseModel):
    error_type: str = Field(..., description="'Business Exception' or 'System Exception'")
    keywords: List[str] = Field(..., description="Key terms from the log")
    root_cause: str = Field(..., description="What caused the failure")
    fix: str = Field(..., description="How to fix it")
    resolution: str = Field(..., description="What was done to resolve it")


class IncidentResponse(BaseModel):
    id: str
    error_type: str
    keywords: List[str]
    root_cause: str
    fix: str
    resolution: str


# ── Helpers ───────────────────────────────────────────────────────────────────
def _read_file_or_error(file_content: bytes, filename: str) -> str:
    """Decode uploaded file bytes or raise 400."""
    try:
        return file_content.decode("utf-8")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not decode '{filename}'. Make sure it is a UTF-8 text file.",
        )


def _validate_log_file(file: UploadFile) -> None:
    """Raise 400 if the file is not a .txt file."""
    is_txt = file.filename.endswith(".txt") if file.filename else False
    is_plain = (file.content_type or "").startswith("text/plain")
    if not (is_txt or is_plain):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt files are supported.",
        )


def _load_incidents() -> list[dict]:
    with open(INCIDENTS_FILE, "r") as f:
        return json.load(f)


def _save_incidents(incidents: list[dict]) -> None:
    with open(INCIDENTS_FILE, "w") as f:
        json.dump(incidents, f, indent=2)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def read_root():
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
async def analyze_log_agentic(file: UploadFile = File(...), _: None = Depends(verify_api_key)):
    """
    🤖 **Agentic endpoint** — Claude decides which tools to call, loops through them,
    and returns a full incident report with transparent reasoning steps.

    Response includes:
    - **final_report**: The complete incident analysis
    - **agent_steps**: Every tool Claude called (classify → search → fix…)
    - **iterations**: How many reasoning loops Claude took
    """
    _validate_log_file(file)
    content = await file.read()
    log_text = _read_file_or_error(content, file.filename or "upload.txt")

    if not log_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    logger.info("Received log for agentic analysis (%d chars)", len(log_text))
    try:
        result = engine.run_agent(log_text)
        return result
    except EnvironmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Agent error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {exc}",
        )


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_log_file(file: UploadFile = File(...), _: None = Depends(verify_api_key)):
    """
    Classic v1 endpoint — still fully powered by the Claude agent internally.
    Returns only the final analysis text for backward compatibility.
    """
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
def add_incident(incident: NewIncident, _: None = Depends(verify_api_key)):
    """
    ➕ Add a newly resolved incident to the knowledge base.

    This is how the agent learns over time — every real incident you resolve
    can be saved here so future similar failures get matched and resolved faster.
    """
    incidents = _load_incidents()

    # Generate next ID
    existing_ids = [i.get("id", "INC-000") for i in incidents]
    max_num = max((int(i.split("-")[1]) for i in existing_ids if "-" in i), default=0)
    new_id = f"INC-{max_num + 1:03d}"

    new_record = {
        "id": new_id,
        "error_type": incident.error_type,
        "keywords": incident.keywords,
        "root_cause": incident.root_cause,
        "fix": incident.fix,
        "resolution": incident.resolution,
    }
    incidents.append(new_record)
    _save_incidents(incidents)

    logger.info("Added new incident %s (%s)", new_id, incident.error_type)
    return new_record


@app.get("/incidents", response_model=list[IncidentResponse])
def list_incidents(_: None = Depends(verify_api_key)) -> List[dict]:
    """📋 List all past incidents in the knowledge base."""
    return _load_incidents()
