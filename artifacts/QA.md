# Interview Q&A — GenAI Incident Commander

---

## 📌 How to Use This File

- Read the **Q** first. Try to answer in your own words.
- Then read the **A** — short, simple, confident.
- Practice saying the answer out loud. One sentence is enough.

---

## 1️⃣ What is This Project?

---

**Q: Tell me about your project in one line.**

A: I built an agentic AI system that reads RPA robot failure logs and automatically finds the root cause, searches past incidents, and suggests exact fixes — powered by Claude AI.

---

**Q: What problem does it solve?**

A: When an RPA robot fails, a human engineer has to spend hours reading thousands of lines of logs. This project does that investigation automatically in seconds.

---

**Q: Who would use this?**

A: RPA Operations teams — people who manage robots doing data entry in SAP, UiPath, or similar tools. When a robot breaks at night, they get a full incident report instantly instead of waiting for an engineer.

---

## 2️⃣ Agentic AI

---

**Q: What is agentic AI?**

A: Normal AI — you give it one question, it gives one answer. Agentic AI — the AI decides what steps to take, calls tools one by one, loops until it has enough information, then writes the final answer. It thinks like a detective, not a calculator.

---

**Q: What is the difference between agentic AI and a basic LLM call?**

A: Basic LLM = one prompt in, one answer out. No memory, no tools.
Agentic = AI decides which tools to call, in what order, loops until confident, then stops on its own.

---

**Q: How does the agentic loop work in your project?**

A: Claude receives the log file. It calls tools one by one — classify error, extract keywords, search past incidents, suggest selector fix. After each tool result, Claude decides whether to call another tool or write the final report. When it has enough information, it stops and returns the report.

---

**Q: When does Claude stop the loop?**

A: Claude returns a signal called `end_turn`. That tells our code — Claude is done, no more tools needed, return the report to the user. We also set a maximum of 10 iterations as a safety limit.

---

**Q: Why did you build the agentic loop manually instead of using LangChain?**

A: Using LangChain would hide what's happening inside. By building it manually, I understand every step — Claude calls a tool, I run the tool, I send the result back, Claude loops again. This means I can explain it clearly in any interview and debug it easily.

---

**Q: What are the 4 tools Claude can call?**

A: 
- `classify_error` — decides if it is a Business Exception or System Exception
- `extract_keywords` — finds important terms from error lines in the log
- `search_past_incidents` — searches the knowledge base for similar past failures
- `suggest_selector_fix` — finds broken SAP selectors and suggests a hardened version

---

**Q: What is a Business Exception vs System Exception?**

A: Business Exception = the robot ran fine but the data was wrong. Example: Customer ID not found in SAP.
System Exception = something broke technically. Example: SAP timed out, selector not found, network error.

---

## 3️⃣ Tech Stack

---

**Q: Why did you choose FastAPI?**

A: FastAPI automatically generates Swagger UI — a testing dashboard — without writing any extra code. It also validates all request and response data automatically. It is fast, modern, and widely used in production.

---

**Q: What is Swagger UI?**

A: A webpage at `/docs` that FastAPI generates automatically. It lists all your API endpoints and lets you test them by clicking buttons — no code needed. Very useful for demos and testing.

---

**Q: What is Uvicorn?**

A: Uvicorn is the server that runs the FastAPI app. Think of FastAPI as the restaurant and Uvicorn as the building it sits in — the building keeps it open and accessible.

---

**Q: What is Pydantic?**

A: Pydantic checks that the data coming in and going out has the correct shape. If someone sends a number where a string is expected, Pydantic catches it automatically and returns a clear error.

---

**Q: What is Docker and why did you use it?**

A: Docker packages the entire app — code, libraries, settings — into one container. That container runs identically on any machine. Without Docker, "it works on my laptop but not on the server" is a common problem. Docker eliminates that.

---

**Q: What is a Dockerfile?**

A: A recipe file. It tells Docker — start with Python 3.11, install these libraries, copy this code, run this command. Docker follows the recipe and builds a ready-to-run container.

---

**Q: Where is the app deployed?**

A: Render.com — a cloud platform. It pulls the code from GitHub, builds the Docker container, and serves it on the internet at `https://genai-incident-commander.onrender.com`.

---

**Q: Why are there environment variables like ANTHROPIC_API_KEY?**

A: API keys are secrets — like passwords. You never put them inside code or Docker images because anyone could read them. Instead, you pass them separately at runtime. On local — via `.env` file. On Render — via the Environment settings page.

---

## 4️⃣ Knowledge Base

---

**Q: What is the knowledge base in this project?**

A: A JSON file called `past_incidents.json` that stores details of past RPA failures — what the error was, what caused it, and how it was fixed. The agent searches this file every time it analyzes a new log.

---

**Q: How does the agent search the knowledge base?**

A: Keyword matching. The agent extracts important words from the current log, then scores each past incident by how many keywords overlap. The top 2 matches are returned to Claude.

---

**Q: Is this RAG (Retrieval Augmented Generation)?**

A: It is a simplified version of RAG. True RAG uses a vector database and semantic search — meaning it finds similar meaning, not just matching words. This project uses keyword matching on a JSON file, which is simpler but effective for this use case.

---

**Q: How does the knowledge base grow over time?**

A: Via the `POST /incidents` endpoint. After a real RPA failure is resolved, an engineer adds it to the knowledge base. Next time a similar failure happens, the agent finds it and uses the past fix.

---

## 5️⃣ Security & Authentication

---

**Q: How is the API secured?**

A: Every endpoint (except the health check) requires an `X-API-Key` header. If the key is missing or wrong, the server returns 401 Unauthorized and blocks the request.

---

**Q: Why is `.env` in `.gitignore`?**

A: The `.env` file contains API keys — secrets. If it gets pushed to GitHub, anyone in the world can see it and steal the keys. `.gitignore` tells Git to never include that file in commits.

---

**Q: What happens if someone sends a PDF instead of a .txt file?**

A: The server returns a 400 Bad Request error immediately. The file validation runs before anything reaches Claude, so no wasted API calls.

---

## 6️⃣ Testing

---

**Q: How many tests does this project have?**

A: 42 tests total — 25 unit tests and 17 integration tests.

---

**Q: What is the difference between unit tests and integration tests?**

A: Unit tests — test one function in isolation. Example: does `classify_error()` return "Business Exception" for this log?
Integration tests — test the full API end to end. Example: does `POST /analyze/agent` return 200 with the correct JSON shape?

---

**Q: Do the tests need a real Claude API key?**

A: No. Claude is mocked in the tests — we replace it with a fake that returns a fixed response. This means tests run fast, free, and offline. All 42 tests pass without any API key.

---

**Q: Why is mocking important in tests?**

A: Real Claude API calls cost money and take time. In tests, you want to run hundreds of checks instantly and for free. Mocking replaces the real API with a fake that behaves predictably.

---

## 7️⃣ Market Trends

---

**Q: What is the current trend in AI development?**

A: The market is moving from basic LLM calls to agentic AI. Companies want AI that can take actions, use tools, make decisions, and complete multi-step tasks — not just answer one question.

---

**Q: What are popular agentic frameworks right now?**

A: LangChain, LangGraph, CrewAI, AutoGen, and Haystack. This project does NOT use any of them — the loop is built manually, which shows deeper understanding.

---

**Q: What is the difference between LangChain and LangGraph?**

A: LangChain is for simple linear chains — step 1, step 2, step 3.
LangGraph is for complex flows with loops, branches, and multiple agents working together. LangGraph is the newer, more powerful one.

---

**Q: What is RAG and why is it popular?**

A: RAG = Retrieval Augmented Generation. Instead of relying only on what the AI was trained on, RAG searches a database first and gives that context to the AI before it answers. Used heavily in document Q&A, customer support bots, and knowledge management tools.

---

**Q: What is a vector database?**

A: A database that stores meaning, not just text. You convert text into numbers (called embeddings) that represent meaning. Then you search by similarity — finding text with similar meaning even if the words are different. Popular ones: Pinecone, Weaviate, ChromaDB.

---

**Q: What is the difference between this project and ChatGPT?**

A: ChatGPT is a general chatbot — you type a question, it answers. This project is domain-specific — it only analyzes RPA logs, uses specialist tools, has a knowledge base, and produces structured incident reports. It is purpose-built, not general purpose.

---

**Q: What would you add next to make this production-ready?**

A: 
- Replace JSON file with a proper database (PostgreSQL)
- Add vector search for smarter knowledge base matching
- Add a dashboard to track all past incidents
- Add Slack/email notifications when a critical failure is detected
- Add user login so different teams have different access

---

**Q: What is the future of RPA + AI?**

A: Traditional RPA is rule-based — robots follow fixed scripts. The future is Agentic RPA — AI decides what to do next based on what it sees on screen. Companies like UiPath and Automation Anywhere are already building AI-native automation. This project is a small example of that direction.

---

## 8️⃣ Quick Fire — One Line Answers

---

**Q: What language is this written in?** — Python

**Q: What framework handles the API?** — FastAPI

**Q: What AI model does it use?** — Claude claude-opus-4-8 by Anthropic

**Q: How many tools does Claude have?** — 4

**Q: Where is it deployed?** — Render.com

**Q: How is it containerized?** — Docker

**Q: How many tests?** — 42 (25 unit + 17 integration)

**Q: What is the knowledge base format?** — JSON flat file

**Q: What header is used for authentication?** — X-API-Key

**Q: What does end_turn mean?** — Claude is done, no more tools needed, return the report

**Q: What port does the app run on?** — 8000

**Q: Where is the Swagger UI?** — /docs

**Q: Where is the browser UI?** — /ui

**Q: What is the live URL?** — https://genai-incident-commander.onrender.com/ui

---

*Prepared for interview readiness — GenAI Incident Commander project*
