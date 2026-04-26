# ── Production Image ──────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
COPY backend/runtime.txt backend/runtime.txt
RUN pip install --no-cache-dir -r backend/runtime.txt

# Install observability SDK from local source
# Note: Commented out for Cloud Build - SDK directory not in build context
# TODO: Publish ai-sre-observability-sdk to PyPI and add to runtime.txt
# COPY ai-sre-observability/sdk /tmp/ai-sre-observability-sdk
# RUN pip install --no-cache-dir /tmp/ai-sre-observability-sdk && rm -rf /tmp/ai-sre-observability-sdk

# App code layer — only this changes on code edits
COPY backend/ backend/
COPY skills/  backend/skills/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
