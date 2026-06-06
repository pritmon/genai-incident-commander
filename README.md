<div align="center">

# 🤖 GenAI Incident Commander

![Tests](https://img.shields.io/badge/Tests-42%20passing-success?style=for-the-badge&logo=pytest)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Claude](https://img.shields.io/badge/Claude_AI-Anthropic-blueviolet?style=for-the-badge)
![Python](https://img.shields.io/badge/Python_3.9+-3776AB?style=for-the-badge&logo=python)

**An agentic AI-powered API that analyzes RPA failure logs, classifies errors, searches past incidents, and suggests exact fixes — powered by Claude AI (Anthropic).**

🌐 **Live Demo:** [https://genai-incident-commander.onrender.com/ui](https://genai-incident-commander.onrender.com/ui)

</div>

---

## 📖 Overview

The **GenAI Incident Commander** is a production-ready FastAPI application for RPA Ops teams. Instead of one big prompt → one answer, it uses a **true agentic loop** — Claude AI calls specialized tools step by step, reasons through the evidence, and produces a structured incident report.

**The agent automatically:**
1. 🔍 **Classifies the error** — Business Exception or System Exception?
2. 🧠 **Extracts keywords** — what components, transactions, and selectors are involved?
3. 📚 **Searches past incidents** — have we seen this before? What fixed it last time?
4. 🛠️ **Suggests exact SAP selector fixes** — corrected XML you can paste straight into UiPath
5. 📋 **Writes a full incident report** — root cause, priority, recommended actions

---

## 🤖 Why Agentic?

Imagine you have a robot factory. Your bots do boring data-entry jobs every day — but sometimes one breaks. A human engineer has to spend hours reading thousands of lines of robot logs to figure out why.

**This project fixes that using AI — but not just any AI call:**

| Approach | What it does |
|---|---|
| Basic LLM call | One prompt → one answer. No memory, no tools. |
| RAG | Searches a database first, then answers. |
| ✅ **Agentic (this project)** | AI decides which tools to use, calls them in sequence, loops until confident, then reports. |

The agent acts like a real senior engineer: checks the error type, searches old case files, looks up the broken selector, then writes its findings. **You didn't tell it what to do — it decided.**

---

## ⚙️ Tech Stack

### 🖥️ Backend
| Technology | What it does |
|---|---|
| **Python 3.11** | The programming language everything is written in |
| **FastAPI** | Receives requests from users over the internet and sends responses back |
| **Uvicorn** | The server that keeps the app running and listening for requests |
| **Pydantic** | Validates that request and response data has the correct shape |

### 🤖 AI & Agentic Layer
| Technology | What it does |
|---|---|
| **Claude claude-opus-4-8 (Anthropic)** | The AI brain — reads the log, calls tools, writes the incident report |
| **Anthropic SDK** | Official Python library to talk to Claude AI |
| **Agentic Loop** | Claude decides which tools to call, loops until confident, then stops — built manually without any framework |
| **4 Specialist Tools** | classify_error, extract_keywords, search_past_incidents, suggest_selector_fix |

### 🗄️ Knowledge Base
| Technology | What it does |
|---|---|
| **past_incidents.json** | Flat-file database — stores past RPA failures, searched by keyword matching |

### 🔐 Security
| Technology | What it does |
|---|---|
| **API Key Auth** | Protects all endpoints — caller must send correct key in X-API-Key header |

### 🧪 Testing
| Technology | What it does |
|---|---|
| **pytest (42 tests)** | Automated tests — 25 unit tests + 17 integration tests, all pass without an API key |

### 🐳 Containerization & Deployment
| Technology | What it does |
|---|---|
| **Docker** | Packages the entire app into a container so it runs identically anywhere |
| **Render.com** | Cloud platform that hosts the Docker container and serves it on the internet |
| **Swagger UI** | Auto-generated testing dashboard at /docs — test all endpoints without writing code |

---

## 📂 Project Structure

```text
genai-incident-commander/
├── app/
│   ├── __init__.py          # Package init
│   ├── main.py              # FastAPI app, routes, API key auth
│   ├── engine.py            # Claude agentic loop (tool-use)
│   └── tools.py             # 4 specialist tools the agent calls
├── data/
│   ├── rpa_logs.txt         # Sample SAP error log for testing
│   └── past_incidents.json  # Knowledge base (grows over time)
├── tests/
│   ├── test_tools.py        # 25 unit tests (no API key needed)
│   └── test_api.py          # 17 integration tests (mocked)
├── .env                     # Your secrets (never committed)
├── .env.example             # Template — copy this to .env
├── .gitignore               # Protects .env from being committed
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

---

## 💻 Local Setup

**1. Clone the repository**
```bash
git clone https://github.com/pritmon/genai-incident-commander.git
cd genai-incident-commander
```

**2. Create a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure your keys**
```bash
cp .env.example .env
```
Edit `.env` and add your keys:
```env
ANTHROPIC_API_KEY=sk-ant-...       # From console.anthropic.com
API_KEY=your-secret-key-here       # Any strong string you choose
```

**5. Start the server**
```bash
uvicorn app.main:app --reload --port 8000
```
Open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## 🔐 Authentication

All endpoints (except `GET /`) require an `X-API-Key` header:

```bash
curl -X POST http://localhost:8000/analyze/agent \
  -H "X-API-Key: your-secret-key-here" \
  -F "file=@data/rpa_logs.txt"
```

Set `API_KEY` in your `.env` file. If not set, auth is disabled (useful for local dev).

---

## 📈 API Endpoints

### `POST /analyze/agent` — Full Agentic Analysis ⭐
Returns the complete report **plus every tool the agent called** so you can see its reasoning.

```bash
curl -X POST http://localhost:8000/analyze/agent \
  -H "X-API-Key: your-key" \
  -F "file=@data/rpa_logs.txt"
```

```json
{
  "final_report": "# 🚨 RPA INCIDENT REPORT...",
  "agent_steps": [
    { "tool": "classify_error",       "args": {} },
    { "tool": "extract_keywords",     "args": {} },
    { "tool": "suggest_selector_fix", "args": {} },
    { "tool": "search_past_incidents","args": { "keywords": ["btn_save", "VA01"] } }
  ],
  "iterations": 3
}
```

### `POST /analyze` — Classic Endpoint (backward-compatible)
Returns only the final report text.

### `POST /incidents` — Add to Knowledge Base
Teach the agent from resolved incidents so future failures get matched faster.

```bash
curl -X POST http://localhost:8000/incidents \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "error_type": "System Exception",
    "keywords": ["btn_save", "VA01", "selector"],
    "root_cause": "SAP dynamic ID changed after upgrade",
    "fix": "Add title and parentid to selector",
    "resolution": "Updated selector, redeployed bot"
  }'
```

### `GET /incidents` — List Knowledge Base
See all stored past incidents.

---

## 🐳 Docker

**Build and run locally with Docker:**

```bash
docker build -t genai-incident-commander .

docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e API_KEY=your-secret-key \
  genai-incident-commander
```

Open **http://localhost:8000/ui** — the app runs identically to the cloud version.

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

All 42 tests run **without an API key** (Claude calls are mocked).

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER / CLIENT                        │
│              Browser UI  /  curl  /  Swagger                │
└─────────────────────┬───────────────────────────────────────┘
                      │  HTTP request + log file
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI  (main.py)                        │
│   • Validates file (.txt only)                              │
│   • Checks API key (X-API-Key header)                       │
│   • Routes to correct endpoint                              │
└─────────────────────┬───────────────────────────────────────┘
                      │  log text
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Claude Agentic Loop  (engine.py)               │
│                                                             │
│   Claude ──calls──► classify_error()                        │
│   Claude ──calls──► extract_keywords()                      │
│   Claude ──calls──► search_past_incidents()  ◄── JSON DB    │
│   Claude ──calls──► suggest_selector_fix()                  │
│   Claude ──loops until confident──► writes final report     │
└─────────────────────┬───────────────────────────────────────┘
                      │  JSON response
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                        USER / CLIENT                        │
│         final_report + agent_steps + iterations             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🤖 How the Agentic Loop Works

```
Log file
   ↓
Claude receives log + tool definitions
   ↓
Claude calls → classify_error()
Claude calls → extract_keywords()
Claude calls → suggest_selector_fix()
Claude calls → search_past_incidents()  ← searches knowledge base
Claude calls → search_past_incidents()  ← searches again with refined terms
   ↓
Claude writes final incident report
```

Claude decides which tools to call and in what order — **you don't tell it**. That's what makes it agentic.

---

<div align="center">
  <i>Built with FastAPI + Claude AI (Anthropic) · Agentic · Tested · Secure</i>
</div>
