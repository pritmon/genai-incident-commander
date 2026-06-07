# =============================================================================
# __init__.py — Package marker for the app/ folder
#
# PURPOSE:
#   This file tells Python that the app/ folder is a package.
#   Without this file, Python cannot import from app.engine, app.tools, etc.
#   It contains no logic — its presence alone is what matters.
#
# FILES IN THIS PACKAGE:
#   engine.py      → Claude AI agentic loop (the brain)
#   tools.py       → 4 specialist tools Claude can call
#   main.py        → FastAPI server, routes, and API key auth
#   static/        → Browser UI (index.html)
# =============================================================================
