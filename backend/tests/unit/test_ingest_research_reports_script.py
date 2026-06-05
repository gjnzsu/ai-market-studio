import importlib.util
from pathlib import Path

import httpx
import respx


SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "ingest_research_reports.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "ingest_research_reports", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_iter_pdf_files_finds_top_level_pdfs_only(tmp_path):
    script = load_script()
    top_level = tmp_path / "report.pdf"
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    nested = nested_dir / "nested.pdf"
    top_level.write_bytes(b"%PDF-1.4")
    nested.write_bytes(b"%PDF-1.4")

    assert script.iter_pdf_files(tmp_path, recursive=False) == [top_level]
    assert script.iter_pdf_files(tmp_path, recursive=True) == [nested, top_level]


def test_ingest_pdf_posts_to_rag_ingest_endpoint(tmp_path):
    script = load_script()
    pdf = tmp_path / "fx-report.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    with respx.mock(base_url="http://rag-service") as mock:
        route = mock.post("/ingest/pdf").mock(
            return_value=httpx.Response(200, json={"document_id": "fx-report"})
        )

        result = script.ingest_pdf(
            pdf,
            rag_service_url="http://rag-service",
            document_type="research_report",
        )

    assert result == {"document_id": "fx-report"}
    assert route.called
    request = route.calls[0].request
    assert "multipart/form-data" in request.headers["content-type"]


def test_ingest_directory_dry_run_does_not_call_rag_service(tmp_path):
    script = load_script()
    pdf = tmp_path / "fx-report.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    results = script.ingest_directory(
        tmp_path,
        rag_service_url="http://rag-service",
        document_type="research_report",
        dry_run=True,
    )

    assert results == [{"file": str(pdf), "status": "dry-run"}]
