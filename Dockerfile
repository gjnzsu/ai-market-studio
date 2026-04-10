# ── Stage 1: Builder (all deps) ───────────────────────────────────────────────
# BuildKit registry cache: pip packages persist in GCR as image layers,
# so subsequent builds restore them without re-downloading from PyPI.
FROM python:3.12-slim AS builder

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip,id=pip-builder \
    pip install --no-cache-dir -r backend/requirements.txt

# ── Stage 2: Production (runtime deps only) ───────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY backend/runtime.txt backend/runtime.txt
RUN --mount=type=cache,target=/root/.cache/pip,id=pip-prod \
    pip install --no-cache-dir -r backend/runtime.txt

# App code layer — only this changes on code edits
COPY backend/ backend/
COPY skills/  backend/skills/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
