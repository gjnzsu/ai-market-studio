# ── Stage 1: Builder (all deps) ───────────────────────────────────────────────
# BuildKit registry cache: pip packages persist in GCR as image layers,
# so subsequent builds restore them without re-downloading from PyPI.
FROM python:3.12-slim AS builder

WORKDIR /app

COPY ai-market-studio/backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# ── Stage 2: Production (runtime deps only) ───────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY ai-market-studio/backend/runtime.txt backend/runtime.txt
RUN pip install --no-cache-dir -r backend/runtime.txt

# Install observability SDK from local source
# Note: In production, replace with: ai-sre-observability-sdk==0.1.0 from PyPI
COPY ai-sre-observability/sdk /tmp/ai-sre-observability-sdk
RUN pip install --no-cache-dir /tmp/ai-sre-observability-sdk && rm -rf /tmp/ai-sre-observability-sdk

# App code layer — only this changes on code edits
COPY ai-market-studio/backend/ backend/
COPY ai-market-studio/skills/  backend/skills/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
