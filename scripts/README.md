# Scripts

Utility scripts for testing and documentation.

## Screenshot Capture Scripts

Located in `screenshots/` - Playwright-based scripts for capturing UI screenshots:

- `shot_06_capture.py` - Capture inline chart in assistant chat bubble
- `shot_f7_live.py` - Capture market insight summary feature
- `shot_f7_recon.py` - Capture RAG response with sources

**Usage:**
```bash
python scripts/screenshots/shot_06_capture.py
```

## E2E Test Scripts

- `test_dashboard.py` - Playwright E2E test for dashboard functionality

**Usage:**
```bash
python scripts/test_dashboard.py
```

## RAG Ingestion Scripts

- `ingest_research_reports.py` - Upload local PDF research reports to an external ai-rag-service instance.

**Dry run:**
```bash
python scripts/ingest_research_reports.py "C:\path\to\research-reports" --dry-run
```

**Upload PDFs:**
```bash
$env:RAG_SERVICE_URL="http://localhost:8000"
python scripts/ingest_research_reports.py "C:\path\to\research-reports" --recursive
```

The script reads `RAG_SERVICE_URL` by default and also accepts `--rag-service-url`.
It does not store service credentials or personal filesystem paths.

**Note:** For comprehensive test suites, see `backend/tests/` directory.
