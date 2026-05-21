$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    uv run --with ruff==0.8.0 ruff check backend tests

    $env:PYTHONPATH = "."
    uv run pytest `
        backend\tests\unit `
        backend\tests\agent `
        backend\tests\e2e\test_chat_api.py `
        backend\tests\e2e\test_gateway_integration.py `
        backend\tests\e2e\test_rag_integration.py `
        backend\tests\e2e\test_pdf_export.py `
        backend\tests\e2e\test_dashboard_api.py `
        backend\tests\e2e\test_correlation_integration.py `
        backend\tests\e2e\test_sub_agents.py `
        -q
}
finally {
    Pop-Location
}
