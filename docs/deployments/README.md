# Deployment History

Detailed deployment summaries and integration documentation.

## 2026-04-23 - AI SRE Observability Integration
**File:** `2026-04-23-observability-integration.md`

Integrated AI SRE Observability Platform for real-time LLM cost tracking.

**Key Changes:**
- Integrated observability SDK into backend
- Configured Prometheus scraping
- Imported 3 Grafana dashboards
- Restored supporting services (RAG, AI Gateway, Prometheus, Grafana)

**Metrics:**
- Real-time LLM cost tracking: ~$0.0072 per query
- Token usage: 11,064 tokens tracked
- Performance: <10ms overhead

## 2026-04-18 - PDF Export & AI Gateway Production Deployment
**File:** `2026-04-18-pdf-export-ai-gateway.md`

Fixed AI Gateway authentication and added PDF export feature.

**Key Changes:**
- Fixed AI Gateway authentication (updated secret with real OpenAI API key)
- Added PDF export endpoint (`POST /api/export/pdf`)
- Created comprehensive PDF export test suite (8 tests, 93% coverage)
- Updated frontend prompts with FRED API example

**Verification:**
- Chat endpoint working
- AI Gateway authenticated and routing correctly
- PDF export generating valid PDFs
- FRED API queries working
