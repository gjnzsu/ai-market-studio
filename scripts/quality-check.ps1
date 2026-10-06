param([string]$PythonExecutable = "python")

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    & $PythonExecutable -m ruff check backend
    if ($LASTEXITCODE -ne 0) { throw "Lint failed with exit code $LASTEXITCODE" }

    $env:PYTHONPATH = "."
    & $PythonExecutable -m pytest `
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
    if ($LASTEXITCODE -ne 0) { throw "Tests failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
