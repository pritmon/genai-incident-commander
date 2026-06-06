# ── Stage 1: Start with a clean lightweight Python 3.11 machine ──────────────
# "slim" means minimal size — only what Python needs, nothing extra
FROM python:3.11-slim

# ── Stage 2: Set the working directory inside the container ───────────────────
# All commands from here run inside /app folder
# Think of it like: cd /app
WORKDIR /app

# ── Stage 3: Copy requirements.txt first (before copying all code) ────────────
# Why first? Docker caches this layer — if requirements didn't change,
# it won't reinstall libraries every time you rebuild. Saves time.
COPY requirements.txt .

# ── Stage 4: Install all Python libraries ─────────────────────────────────────
# --no-cache-dir = don't save install cache (keeps container size small)
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 5: Copy all project files into the container ────────────────────────
# The .dockerignore file controls what gets excluded (venv, .env, etc.)
COPY . .

# ── Stage 6: Tell Docker which port the app runs on ───────────────────────────
# This is just documentation — actual port mapping happens in docker run command
EXPOSE 8000

# ── Stage 7: Start the server when container runs ─────────────────────────────
# --host 0.0.0.0 = accept connections from outside the container
# --port 8000    = run on port 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
