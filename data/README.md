# data/ — Knowledge Base & Sample Logs

## 📁 Files in This Folder

---

### 📄 past_incidents.json
**PURPOSE:** The knowledge base of this project.

Stores details of every past RPA failure that has been resolved. The Claude AI agent searches this file during every analysis to find similar past failures and apply the same fix.

**More incidents added = smarter agent.**

Each entry has these fields:

| Field | What it means |
|---|---|
| `id` | Auto-generated ID — INC-001, INC-002… |
| `error_type` | `Business Exception` or `System Exception` |
| `keywords` | Key terms used to match against new logs |
| `root_cause` | What caused the failure |
| `fix` | How to fix it |
| `resolution` | What was actually done to resolve it |

**How to add new incidents:**
```bash
curl -X POST https://genai-incident-commander.onrender.com/incidents \
  -H "X-API-Key: incident-commander-2024" \
  -H "Content-Type: application/json" \
  -d '{
    "error_type": "System Exception",
    "keywords": ["btn_save", "selector", "SAP"],
    "root_cause": "SAP selector broke after upgrade",
    "fix": "Update selector with title and parentid",
    "resolution": "Redeployed bot with hardened selector"
  }'
```

---

### 📄 rpa_logs.txt
**PURPOSE:** Sample RPA log file for testing and demos.

Use this file to test the application — upload it via the UI at `/ui` or send it via curl to `/analyze/agent`. It contains a realistic SAP RPA failure log with both a selector error and a missing Customer ID error.
