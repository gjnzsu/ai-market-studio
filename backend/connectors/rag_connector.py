from typing import Any

import httpx

from backend.config import settings


class RAGConnector:
    def __init__(self, url: str = settings.rag_service_url):
        self.url = url

    @staticmethod
    def _normalize_sources(raw_sources: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_sources, list):
            return []

        normalized_sources: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        for source in raw_sources:
            if isinstance(source, dict):
                source_name = (
                    source.get("title")
                    or source.get("document_id")
                    or source.get("name")
                    or "Unknown source"
                )
                # Deduplicate by source name
                if source_name not in seen_names:
                    seen_names.add(source_name)
                    normalized_sources.append({"name": source_name, **source})
            else:
                source_str = str(source)
                if source_str not in seen_names:
                    seen_names.add(source_str)
                    normalized_sources.append({"name": source_str})
        return normalized_sources

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            key: value
            for key, value in payload.items()
            if key not in {"sources", "results", "answer", "type"}
        }
        normalized["type"] = "rag"
        normalized["answer"] = payload.get("answer", "")
        normalized["sources"] = self._normalize_sources(
            payload.get("sources", payload.get("results", []))
        )
        return normalized

    @staticmethod
    def _error_payload(error: str) -> dict[str, Any]:
        return {
            "type": "rag",
            "answer": "",
            "sources": [],
            "error": error,
        }

    async def query_research(self, question: str) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.url}/query",
                    json={"question": question},
                    timeout=10.0,
                )
                resp.raise_for_status()
                return self._normalize_payload(resp.json())
            except Exception as e:
                return self._error_payload(str(e))
