<div align="center">
  
# 🤖 GenAI Incident Commander

![Python CI](https://img.shields.io/badge/Python_CI-passing-success?style=for-the-badge&logo=github)
[![Live Demo](https://img.shields.io/badge/Live-Demo-success?style=for-the-badge)](https://genai-incident-commander.onrender.com/docs)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Gemini](https://img.shields.io/badge/Gemini_1.5_Flash-8E75B2?style=for-the-badge&logo=google)

**An intelligent, automated log analysis API that translates complex RPA failures into actionable human insights using Google's Gemini LLM.**

</div>

---

## 📖 Overview

The **GenAI Incident Commander** is a production-ready FastAPI application designed specifically for Robotic Process Automation (RPA) Ops teams. Debugging raw RPA logs can be tedious, time-consuming, and prone to human error. This API acts as a "Senior AI Architect," instantly ingesting log files and leveraging **Gemini 1.5 Flash** (via `google-generativeai`) to automatically:

1. 🔍 **Identify the Root Cause:** Pinpoint exactly why the bot failed.
2. 🛠️ **Suggest UX/UI Fixes:** Provide concrete, corrected SAP UI selectors to resolve the issue.
3. 🏷️ **Classify the Exception:** Categorize the error strictly as a **Business Exception** or a **System Exception**.

This turns hours of manual log reading into a sub-second API call.

---

## � Why is this Useful? (Explained Simply)

Imagine you have a robot factory. Your robots (RPA bots) do all the boring data-entry jobs for you every single day. But sometimes... a robot gets confused and stops working. 

Usually, a human engineer has to spend hours reading through thousands of lines of confusing "robot gibberish" (logs) just to figure out why it broke. 

**This project fixes that using AI!**

Instead of a human reading the logs, you just hand the broken robot's diary to this API. In less than 5 seconds, Google's super-smart Gemini AI reads the whole thing and tells you:
1. **"It broke because the customer ID was missing from the database."** (Root Cause)
2. **"To fix the bot, you need to change this specific button click code to THIS."** (SAP Fixes)
3. **"This wasn't a computer glitch, someone just typed the wrong data!"** (Classification)

It's like having the world's fastest, smartest senior engineer on call 24/7 to instantly fix your automated workforce!

---

## �🚀 Key Features

* **Instant Analysis:** Simply `POST` a `.txt` log file to the `/analyze` endpoint and receive a structured JSON response in seconds.
* **LLM Powered:** Uses Google's state-of-the-art Gemini 1.5 Flash model for deep contextual understanding of system errors.
* **Developer Friendly:** Built on FastAPI, providing out-of-the-box Swagger UI (`/docs`) for easy testing and integration.
* **Robust Error Handling:** Automatically handles empty files, invalid file types, and external API failures gracefully.

---

## ⚙️ Tech Stack

* **Backend Framework:** Python 3.9+, FastAPI, Uvicorn
* **AI Engine:** Google Generative AI (`gemini-2.5-flash`)
* **Environment:** `python-dotenv` for secure credential management

---

## 📂 Project Structure

```text
genai-incident-commander/
├── app/
│   ├── __init__.py      # Package initialization
│   ├── main.py          # FastAPI application & routing logic
│   └── engine.py        # Gemini AI prompt engineering & client calls
├── data/
│   └── rpa_logs.txt     # Sample SAP error logs for testing
├── artifacts/
│   ├── technical_deep_dive.md  # Architectural Q&A and System Design
│   ├── implementation_plan.md  # Simple "Blueprint" of how the parts work
│   └── git_commands_history.md # Record of terminal commands used in build
├── .env                 # (Ignored) Your Google API Key configuration
├── .gitignore           # Prevents leaking sensitive keys
├── requirements.txt     # Standardized list of Python dependencies
└── README.md            # You are reading it!
```

---

## 💻 Local Setup & Installation

Follow these steps to run the Incident Commander directly on your machine.

**1. Clone the repository**
```bash
git clone https://github.com/pritmon/genai-incident-commander.git
cd genai-incident-commander
```

**2. Create a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure your API Key**
Create a `.env` file in the root directory and add your Google AI Studio API key:
```env
GOOGLE_API_KEY=your_actual_api_key_here
```

**5. Start the server!**
```bash
uvicorn app.main:app --reload --port 8000
```
*Navigate to `http://localhost:8000/docs` in your browser to interact with the API.*

---

## 📈 Example Usage

You can test the API using `curl` from your terminal!

**Request:**
```bash
curl -X POST -F "file=@data/rpa_logs.txt" http://localhost:8000/analyze
```

**Response:**
```json
{
  "analysis": "1. Root Cause: BusinessRuleException caused by missing Customer ID 'LL-987'...\n2. SAP Selector fixes: Update <sap id='btn_save' /> to include parent window attributes...\n3. Classification: Business Exception"
}
```

---
<div align="center">
  <i>Architected with ❤️ using FastAPI & Gemini</i>
</div>
