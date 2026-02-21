This plan explains **how** we built the GenAI Incident Commander and **why** each part is important. Think of this as the "Blueprint" for the system.

---

## 1. Project Organization (The "Skeleton")

Before writing code, we created a small, neat folder structure to keep things organized.

*   **`data/`**: The "In-box" where you drop your broken RPA log files.
*   **`app/`**: The "Engine Room" where all the Python brain-power lives.
*   **`artifacts/`**: The "Filing Cabinet" where we store helpful documents (like the git commands history).

---

## 2. Core Components (The "Engine Parts")

### A. The Front Door (`app/main.py`) - *The Receptionist*

*   **What it does:** It sets up the actual web server using FastAPI. It creates the `/analyze` route where people can upload files.
*   **Why it's needed:** We need a way for the outside world (or a browser) to talk to our Python code. The `main.py` is like a receptionist who takes the uploaded file, makes sure it's a `.txt` file, and hands it off to the AI expert.

### B. The AI Brain (`app/engine.py`) - *The Expert Log Reader*

*   **What it does:** It takes the text from the log file, logs into Google Gemini (using the `.env` key), and asks the AI our specific questions based on the `system_instruction`.
*   **Why it's needed:** This is where the magic happens. We don't want to code the rules for every possible error; we want Google's AI to read it dynamically. This file handles all the complex talking with the LLM.

### C. The Instructions (`app/engine.py` Prompts) - *The Rule Book*

*   **What it does:** Within `engine.py`, we wrote a strict set of rules for Gemini: "You are a Senior AI Architect... Find the Root Cause, Suggest SAP Fixes, and Classify as Business/System."
*   **Why it's needed:** AI models will ramble if you let them. By giving it a strict "Rule Book" (System Prompt), we force it to always give us the exact 3-part answer we need.

---

## 3. Configuration Files (The "Utility Belt")

### A. The Lockbox (`.env` and `.gitignore`)

*   **What it does:** The `.env` file holds the secret `GOOGLE_API_KEY`. The `.gitignore` file tells Git to *never* upload the `.env` file to the internet.
*   **Why it's needed:** If we upload our Google Key to GitHub, someone else could steal it and use it for free! This keeps us safe.

### B. The Shopping List (`requirements.txt`)

*   **What it does:** A simple text file that lists `fastapi`, `uvicorn`, `google-generativeai`, etc.
*   **Why it's needed:** When we put this code on another computer (or Render.com), the computer doesn't know what it needs to run our code. This list tells it exactly what to download automatically.
