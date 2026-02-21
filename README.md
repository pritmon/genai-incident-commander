# GenAI Incident Commander

A FastAPI application powered by Gemini 1.5 Flash to automatically analyze RPA logs, identify root causes, and suggest SAP selector fixes.

## Project Structure
```text
genai-incident-commander/
├── app/
│   ├── __init__.py
│   ├── main.py          <-- The FastAPI Logic
│   └── engine.py        <-- The Gemini/LLM Logic
├── data/
│   └── rpa_logs.txt     <-- Your Test Data
├── .env                 <-- Your Google API Key
├── .gitignore           <-- Prevents leaking keys
├── requirements.txt     <-- For Render/GitHub
└── README.md            # The "God-tier" Documentation
```

## Setup & Running
1. Add your Google API Key in `.env`.
2. Install dependencies: `pip install -r requirements.txt`
3. Run the server: `uvicorn app.main:app --reload`
4. Access the Swagger UI at `http://localhost:8000/docs` to test log uploads!
