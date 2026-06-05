"""Ingest local research-report PDFs into an external ai-rag-service instance."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import httpx

DEFAULT_RAG_SERVICE_URL = "http://localhost:8000"
DEFAULT_DOCUMENT_TYPE = "research_report"


def iter_pdf_files(source_dir: Path, recursive: bool = False) -> list[Path]:
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(source_dir.glob(pattern))


def ingest_pdf(
    file_path: Path,
    rag_service_url: str,
    document_type: str = DEFAULT_DOCUMENT_TYPE,
    timeout: float = 120.0,
) -> dict[str, Any]:
    with file_path.open("rb") as file_handle:
        files = {"file": (file_path.name, file_handle, "application/pdf")}
        data = {"document_type": document_type}
        response = httpx.post(
            f"{rag_service_url.rstrip('/')}/ingest/pdf",
            files=files,
            data=data,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()


def ingest_directory(
    source_dir: Path,
    rag_service_url: str,
    document_type: str = DEFAULT_DOCUMENT_TYPE,
    recursive: bool = False,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    pdf_files = iter_pdf_files(source_dir, recursive=recursive)
    results: list[dict[str, Any]] = []

    for pdf_file in pdf_files:
        if dry_run:
            results.append({"file": str(pdf_file), "status": "dry-run"})
            continue

        try:
            result = ingest_pdf(
                pdf_file,
                rag_service_url=rag_service_url,
                document_type=document_type,
            )
            results.append({"file": str(pdf_file), "status": "success", "result": result})
        except Exception as exc:
            results.append({"file": str(pdf_file), "status": "error", "error": str(exc)})

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest local PDF research reports into ai-rag-service."
    )
    parser.add_argument("source_dir", type=Path, help="Directory containing PDF files.")
    parser.add_argument(
        "--rag-service-url",
        default=os.getenv("RAG_SERVICE_URL", DEFAULT_RAG_SERVICE_URL),
        help="Base URL for ai-rag-service. Defaults to RAG_SERVICE_URL or localhost.",
    )
    parser.add_argument(
        "--document-type",
        default=DEFAULT_DOCUMENT_TYPE,
        help="Document type sent to the ingestion endpoint.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Find PDF files recursively under source_dir.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching PDF files without uploading them.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_dir = args.source_dir.expanduser().resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        raise SystemExit(f"Source directory does not exist: {source_dir}")

    results = ingest_directory(
        source_dir=source_dir,
        rag_service_url=args.rag_service_url,
        document_type=args.document_type,
        recursive=args.recursive,
        dry_run=args.dry_run,
    )

    print(f"Found {len(results)} PDF file(s)")
    for item in results:
        print(f"{item['status']}: {item['file']}")
        if item.get("error"):
            print(f"  error: {item['error']}")
        elif item.get("result"):
            print(f"  result: {item['result']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
