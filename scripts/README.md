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

**Note:** For comprehensive test suites, see `backend/tests/` directory.
