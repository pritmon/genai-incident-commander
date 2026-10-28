# GenAI Incident Commander — Internal Demo Script
**For: Wella Account — HCL Internal Discussion**
**Presenter: Pritam Mondal**

---

## 🎯 What Problem This Solves

In Wella's RPA support, when a bot fails:
- Engineer manually reads hundreds of lines of log
- Takes 2–4 hours to classify, find root cause, write report
- No consistency — different engineers write different quality reports
- Same error repeats because there's no searchable history

**This tool does it in 15–30 seconds. Automatically.**

---

## 🏗️ How It Works (30 seconds explanation)

```
Bot fails → writes a log file
        ↓
Upload log to this tool
        ↓
Claude AI reads it and calls 4 specialist tools:
  1. classify_error        → System Exception or Business Exception?
  2. extract_keywords      → What components are involved?
  3. search_past_incidents → Has this happened before?
  4. suggest_selector_fix  → Is a UI selector broken?
        ↓
Claude writes a structured report
        ↓
Engineer gets: root cause + priority + action steps in seconds
```

---

## 🖥️ Live Demo Steps

### Step 1 — Open the live URL
```
https://genai-incident-commander.onrender.com/ui
```
API Key: `incident-commander-2024`

### Step 2 — Upload the Wella demo log
Use file: `data/wella_rpa_demo_log.txt`

This log has 3 real-world failures in one run:
- Invoice INV-WELLA-2026-4821 → **System Exception** (SAP MIRO selector broken)
- Invoice INV-WELLA-2026-4822 → **Business Exception** (Vendor HENKEL-DE-003 payment blocked)
- Invoice INV-WELLA-2026-4823 → **Business Exception** (Duplicate invoice already posted)

### Step 3 — Click Analyze and show the report live

Point out during demo:
- ❌ Section → plain English, no jargon
- 🏷️ Section → exact classification with reason
- ⚡ Section → priority so team knows what to fix first
- 🔍 Section → 3-5 factual bullets, quotes the exact log line
- 🛠️ Section → tells exactly which team does what (AP team, SAP Basis, RPA developer)
- 📚 Section → pulls from historical knowledge base
- 🤖 Section → tells if bot is still running or fully stopped

### Step 4 — Show the Swagger API docs
```
https://genai-incident-commander.onrender.com/docs
```
Show that this is a proper REST API — can be integrated with ServiceNow, Teams alerts, email.

---

## 📊 Show the Observability Dashboards

### Arize AX — LLM Layer
- Every Claude call is traced
- Shows: input log, output report, tokens used, cost, latency
- 13 traces visible — 105k tokens total, $0.67 total cost
- **Key message:** "We can see exactly what Claude is doing — full transparency"

### Datadog — API Layer
- Shows request count, duration, error rate
- Metric: `incident_commander.analysis.success` → count of analyses done
- Metric: `incident_commander.analysis.iterations` → how many tool loops Claude used
- **Key message:** "We monitor the app's health independently of the AI"

---

## 🔄 Wella Applicability

| IKEA Implementation | This Project | Wella Adaptation |
|---|---|---|
| GitHub Copilot + VS Code | Direct Claude API + FastAPI | Either — depends on Wella LLM access |
| Splunk MCP for logs | Upload log file manually | Connect to Wella's log tool via MCP |
| Platform-level RCA | RPA bot-level RCA | Application-level RCA (same approach) |
| Inside IKEA environment | Live on internet (Render) | Deploy inside Wella environment |
| Confluence + Jira via MCP | JSON knowledge base | ServiceNow incidents via MCP |

**The architecture is the same. Only the data sources change.**

---

## ❓ Likely Questions & Answers

**Q: Can this connect to ServiceNow?**
A: Yes — via an MCP connector. Once ServiceNow API details are available, we write a connector that pulls past incidents directly into the knowledge base. Mohit is doing the same for IKEA NowIT.

**Q: Does it need Splunk?**
A: No. It works with any log file — UiPath Orchestrator logs, file-based logs, or logs from any monitoring tool. If Wella has Splunk/Dynatrace, we write an MCP to pull logs automatically.

**Q: How accurate is it?**
A: Classification accuracy is high for structured RPA logs. The quality of root cause depends on log quality — the better the bot's logging, the better the report.

**Q: What LLM does it use?**
A: Claude Opus (Anthropic) — same model Mohit uses at IKEA via GitHub Copilot. We use the direct API. If Wella has GHCP enterprise access, we can switch to that.

**Q: What does it cost?**
A: ~$0.02–$0.08 per analysis based on current usage. For 50 incidents/day that's under $150/month.

**Q: How long to implement for Wella?**
A: 4–6 weeks for initial version:
- Week 1–2: Assess Wella's observability tool and log structure
- Week 3–4: Build MCP connector for Wella's log source
- Week 5–6: Connect to ServiceNow, tune prompts, test with real Wella logs

---

## 🔗 Links

| Resource | URL |
|---|---|
| Live UI | https://genai-incident-commander.onrender.com/ui |
| API Docs | https://genai-incident-commander.onrender.com/docs |
| GitHub | https://github.com/pritmon/genai-incident-commander |
| API Key | `incident-commander-2024` |
