from typing import Any

import httpx

from backend.config import settings


class RAGConnector:
    def __init__(self, url: str = settings.rag_service_url):
        self.url = url

    @staticmethod
    def _normalize_sources(
        raw_sources: Any,
        *,
        deduplicate: bool = True,
    ) -> list[dict[str, Any]]:
        if not isinstance(raw_sources, list):
            return []

        normalized_sources: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        for source in raw_sources:
            if isinstance(source, dict):
                metadata = source.get("metadata", {})
                if not isinstance(metadata, dict):
                    metadata = {}
                title = source.get("title") or metadata.get("title")
                content = source.get("content", "")
                source_name = (
                    title
                    or source.get("document_id")
                    or source.get("name")
                    or "Unknown source"
                )
                # Deduplicate by source name
                if not deduplicate or source_name not in seen_names:
                    seen_names.add(source_name)
                    normalized_source = {
                        "name": source_name,
                        "content": content,
                        "document_id": source.get("document_id", ""),
                        "chunk_id": source.get("chunk_id", ""),
                        "source_type": (
                            source.get("source_type")
                            or metadata.get("source_type")
                            or metadata.get("type", "")
                        ),
                        "excerpt": source.get("excerpt") or content,
                        "score": source.get("score"),
                        "source_url": source.get("source_url") or metadata.get("url", ""),
                        "metadata": metadata,
                    }
                    if title:
                        normalized_source["title"] = title
                    normalized_sources.append(normalized_source)
            else:
                source_str = str(source)
                if source_str not in seen_names:
                    seen_names.add(source_str)
                    normalized_sources.append({"name": source_str})
        return normalized_sources

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        results = payload.get("results", [])
        return {
            "type": "rag",
            "answer": "",
            "sources": self._normalize_sources(results),
            "evidence": self._normalize_sources(results, deduplicate=False),
        }

    @staticmethod
    def _error_payload(error: str) -> dict[str, Any]:
        return {
            "type": "rag",
            "answer": "",
            "sources": [],
            "error": error,
        }

    async def query_research(self, question: str, document_type: str | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                payload: dict[str, Any] = {"query": question, "top_k": 5}
                if document_type == "research_report":
                    payload["collection"] = "research_reports"
                elif document_type and document_type != "general":
                    payload["filters"] = {"document_type": document_type}

                resp = await client.post(
                    f"{self.url}/retrieve",
                    json=payload,
                    timeout=10.0,
                )
                resp.raise_for_status()
                return self._normalize_payload(resp.json())
            except Exception as e:
                return self._error_payload(str(e))
