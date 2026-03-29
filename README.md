# AI Market Studio

A conversational FX market data platform. Ask natural-language questions about exchange rates and get instant inline charts — all in a clean single-pane chat interface with no build step.

> **Vision:** AI-native market intelligence platform that enables natural language–driven data retrieval, automated dashboard generation, and context-aware insights.

![Chat UI](shot_07_chat_ui.png)

---

## Features

### Feature 01 — FX Chat Assistant
- Natural-language queries: *"What is EUR/USD today?"*, *"Compare USD vs JPY and CHF"*
- GPT-4o function calling with five tools: spot rate, multi-pair rates, supported currencies list, dashboard generation, market news
- Conversation history maintained client-side

### Feature 02 — FX Rate Historical Data
- `POST /api/rates/historical` — daily FX rates with in-memory LRU cache (TTL=300s)
- `POST /api/dashboard` — batch panel data fetch (up to 9 panels)
- Supports line trend, bar comparison, and stat summary panel types
- Toggle between live API and mock data via `USE_MOCK_CONNECTOR` env var

### Feature 03 — Market News
- Ask in natural language: *"What's the latest FX news?"*, *"Any news on EUR/USD?"*
- GPT-4o calls the `get_fx_news` tool; results render as inline news cards in the chat bubble
- Free RSS feeds (BBC Business, Investing.com FX, FXStreet) — no paid API key required
- Query filtering and item cap; fully decoupled from rate connector via `USE_MOCK_NEWS_CONNECTOR`
- Mock news connector used in all tests (8+ hardcoded items, deterministic)

### Feature 04 — Conversational Dashboard Generation
- Ask in natural language: *"Show me EUR/USD and GBP/USD trend for the last 5 days"*
- LLM detects chart/visualize/show intent and calls the `generate_dashboard` tool
- Inline Chart.js chart renders directly inside the chat bubble — no tab switching
- Supports line trend (time series) and bar comparison chart types
- Suggested example chips in the UI for quick access

![Conversational Dashboard](shot_08_inline_chart.png)

---

## Architecture

```
Browser — single-pane chat UI (Vanilla JS + Chart.js)
        │
        ▼
FastAPI Backend  (backend/)
   ├── /api/chat              ← GPT-4o agent loop (5 tools)
   ├── /api/rates/historical  ← daily FX rates, LRU cached
   └── /api/dashboard         ← batch panel fetch
        │
        ▼
Connector Layer
   ├── ExchangeRateHostConnector  ← live FX data (exchangerate.host)
   ├── MockConnector              ← deterministic synthetic FX data
   ├── RSSNewsConnector           ← free RSS feeds (BBC, Investing.com, FXStreet)
   └── MockNewsConnector          ← deterministic synthetic news (tests + dev)
```

**GPT-4o tools:** `get_exchange_rate`, `get_exchange_rates`, `get_historical_rates`, `generate_dashboard`, `get_fx_news`

---

## Live Deployment

The app is deployed on Google Kubernetes Engine (GKE):

**http://35.224.3.54/**

| Detail | Value |
|---|---|
| Cluster | `helloworld-cluster` (us-central1) |
| GCP Project | `gen-lang-client-0896070179` |
| Image | `gcr.io/gen-lang-client-0896070179/ai-market-studio:latest` |
| Connector | `USE_MOCK_CONNECTOR=true` |

---

## Quick Start

### Prerequisites
- Python 3.12+
- An [OpenAI API key](https://platform.openai.com/)
- An [exchangerate.host API key](https://exchangerate.host/) (free tier)

### 1. Clone and install

```bash
git clone https://github.com/gjnzsu/ai-market-studio.git
cd ai-market-studio
pip install -r backend/requirements.txt
```

### 2. Configure environment

Create a `.env` file in the repo root:

```env
OPENAI_API_KEY=sk-...
EXCHANGERATE_API_KEY=your_key_here
USE_MOCK_CONNECTOR=true   # set false to use live exchangerate.host data
```

> **Note:** The exchangerate.host free tier has a ~100 req/month quota. Keep `USE_MOCK_CONNECTOR=true` during development to avoid exhausting it.

### 3. Start the server

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Deploy to GKE

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) with GCR auth configured
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) authenticated
- `kubectl` configured for your cluster

### 1. Build and push the image

```bash
gcloud auth configure-docker
docker build -t gcr.io/<PROJECT_ID>/ai-market-studio:latest .
docker push gcr.io/<PROJECT_ID>/ai-market-studio:latest
```

### 2. Get cluster credentials

```bash
gcloud container clusters get-credentials <CLUSTER_NAME> --region <REGION> --project <PROJECT_ID>
```

### 3. Create the Kubernetes secret

```bash
kubectl create secret generic ai-market-studio-secrets \
  --from-literal=OPENAI_API_KEY=<your-openai-key> \
  --from-literal=EXCHANGERATE_API_KEY=<your-key-or-dummy>
```

> Do not commit real API keys to `k8s/secret.yaml`. Always create secrets imperatively.

### 4. Apply manifests

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### 5. Get the external IP

```bash
kubectl get service ai-market-studio --watch
```

Once `EXTERNAL-IP` is assigned, the app is available at `http://<EXTERNAL-IP>/`.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required. OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Model used by the agent |
| `EXCHANGERATE_API_KEY` | — | Required. exchangerate.host API key |
| `USE_MOCK_CONNECTOR` | `false` | Use synthetic FX data instead of live exchangerate.host API |
| `USE_MOCK_NEWS_CONNECTOR` | `false` | Use synthetic news data instead of live RSS feeds |
| `MAX_HISTORICAL_DAYS` | `7` | Max date range per dashboard request |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

---

## Running Tests

```bash
# Unit and E2E API tests
pytest backend/tests/ -v

# Playwright end-to-end test (requires server running on :8000)
python test_dashboard.py
```

> Tests always use `MockConnector` — no API quota consumed.

---

## Project Structure

```
ai-market-studio/
├── backend/
│   ├── main.py              # FastAPI app factory
│   ├── router.py            # API endpoints
│   ├── models.py            # Pydantic request/response models
│   ├── config.py            # Settings (pydantic-settings)
│   ├── cache.py             # In-memory LRU rate cache
│   ├── agent/
│   │   ├── agent.py         # GPT-4o function-calling loop
│   │   └── tools.py         # Tool definitions and dispatch
│   ├── connectors/
│   │   ├── base.py              # Abstract FX connector interface
│   │   ├── news_base.py         # Abstract news connector interface
│   │   ├── exchangerate_host.py
│   │   ├── mock_connector.py
│   │   ├── rss_news_connector.py
│   │   └── mock_news_connector.py
│   └── tests/
│       ├── unit/
│       └── e2e/
├── frontend/
│   └── index.html           # Single-page app (no build step)
├── docs/                    # Design and product documentation
├── test_dashboard.py        # Playwright E2E test
└── .env                     # Local secrets (not committed)
```

---

## Roadmap

| Priority | Theme | Features |
|----------|-------|----------|
| **P0 — Done** | Foundation | Chat assistant, spot & historical FX rates, conversational dashboard, market news, GKE deployment |
| **P1 — Awareness** | Market Intelligence | F7: Market Insight Summary — AI-generated "why is EUR/USD moving?" commentary from news + rate data; F3: Market News (delivered) |
| **P2 — Productivity** | Output Generation | F9: PPT / Excel / PDF report generation; F8: Email sending of insights and reports |
| **P3 — Intelligence** | Research | F5: Web search integration for live market context; F4: Research report generation via RAG pipeline over internal documents |
| **P4 — Data Breadth** | Data & Collaboration | F1: Multi-source market data connectors; F6: Sales/trader commentary capture and retrieval; F12: Scheduled report function |
| **P5 — Advanced** | Platform | F10: Custom agent creation; F11: OCR / document ingestion (scanned reports, PDFs) |
