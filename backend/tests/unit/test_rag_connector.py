import json

import httpx
import pytest
import respx

from backend.connectors.rag_connector import RAGConnector


@pytest.mark.asyncio
async def test_query_research_normalizes_sources_and_preserves_metadata():
    connector = RAGConnector(url="http://mock-rag-service")
    mock_response = {
        "results": [
            {
                "content": "Release checklist and dependencies",
                "document_id": "doc-123",
                "chunk_id": "doc-123:0",
                "metadata": {
                    "source_type": "jira",
                    "title": "Rollout Notes",
                    "type": "research_report",
                },
                "score": 0.91,
                "source_url": "https://example.test/rollout-notes",
            },
            {
                "content": "Fallback source without title",
                "document_id": "doc-456",
                "chunk_id": "doc-456:0",
                "metadata": {"source_type": "pdf"},
                "score": 0.73,
                "source_url": "",
            },
            {
                "content": "A second relevant rollout section",
                "document_id": "doc-123",
                "chunk_id": "doc-123:1",
                "metadata": {
                    "source_type": "jira",
                    "title": "Rollout Notes",
                    "type": "research_report",
                },
                "score": 0.69,
                "source_url": "https://example.test/rollout-notes",
            },
        ],
    }

    with respx.mock(base_url="http://mock-rag-service") as respx_mock:
        request = respx_mock.post("/retrieve").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        result = await connector.query_research("market trends", "research_report")

    assert json.loads(request.calls[0].request.content) == {
        "query": "market trends",
        "top_k": 5,
        "collection": "research_reports",
    }
    assert result == {
        "type": "rag",
        "answer": "",
        "sources": [
            {
                "name": "Rollout Notes",
                "content": "Release checklist and dependencies",
                "document_id": "doc-123",
                "chunk_id": "doc-123:0",
                "source_type": "jira",
                "title": "Rollout Notes",
                "excerpt": "Release checklist and dependencies",
                "score": 0.91,
                "source_url": "https://example.test/rollout-notes",
                "metadata": {
                    "source_type": "jira",
                    "title": "Rollout Notes",
                    "type": "research_report",
                },
            },
            {
                "name": "doc-456",
                "content": "Fallback source without title",
                "document_id": "doc-456",
                "chunk_id": "doc-456:0",
                "source_type": "pdf",
                "excerpt": "Fallback source without title",
                "score": 0.73,
                "source_url": "",
                "metadata": {"source_type": "pdf"},
            },
        ],
        "evidence": [
            {
                "name": "Rollout Notes",
                "content": "Release checklist and dependencies",
                "document_id": "doc-123",
                "chunk_id": "doc-123:0",
                "source_type": "jira",
                "title": "Rollout Notes",
                "excerpt": "Release checklist and dependencies",
                "score": 0.91,
                "source_url": "https://example.test/rollout-notes",
                "metadata": {
                    "source_type": "jira",
                    "title": "Rollout Notes",
                    "type": "research_report",
                },
            },
            {
                "name": "doc-456",
                "content": "Fallback source without title",
                "document_id": "doc-456",
                "chunk_id": "doc-456:0",
                "source_type": "pdf",
                "excerpt": "Fallback source without title",
                "score": 0.73,
                "source_url": "",
                "metadata": {"source_type": "pdf"},
            },
            {
                "name": "Rollout Notes",
                "content": "A second relevant rollout section",
                "document_id": "doc-123",
                "chunk_id": "doc-123:1",
                "source_type": "jira",
                "title": "Rollout Notes",
                "excerpt": "A second relevant rollout section",
                "score": 0.69,
                "source_url": "https://example.test/rollout-notes",
                "metadata": {
                    "source_type": "jira",
                    "title": "Rollout Notes",
                    "type": "research_report",
                },
            },
        ],
    }


@pytest.mark.asyncio
async def test_query_research_maps_document_type_to_retrieve_filter():
    connector = RAGConnector(url="http://mock-rag-service")

    with respx.mock(base_url="http://mock-rag-service") as respx_mock:
        request = respx_mock.post("/retrieve").mock(
            return_value=httpx.Response(200, json={"results": []})
        )

        await connector.query_research("policy", "rulebook")

    assert json.loads(request.calls[0].request.content) == {
        "query": "policy",
        "top_k": 5,
        "filters": {"document_type": "rulebook"},
    }


@pytest.mark.asyncio
async def test_query_research_error_returns_rag_payload_shape():
    connector = RAGConnector(url="http://mock-rag-service")

    with respx.mock(base_url="http://mock-rag-service") as respx_mock:
        respx_mock.post("/retrieve").mock(return_value=httpx.Response(500))

        result = await connector.query_research("fail")

    assert result["type"] == "rag"
    assert result["answer"] == ""
    assert result["sources"] == []
    assert "error" in result
