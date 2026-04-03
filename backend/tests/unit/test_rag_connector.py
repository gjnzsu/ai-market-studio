import httpx
import pytest
import respx

from backend.connectors.rag_connector import RAGConnector


@pytest.mark.asyncio
async def test_query_research_normalizes_sources_and_preserves_metadata():
    connector = RAGConnector(url="http://mock-rag-service")
    mock_response = {
        "answer": "Use the latest AI platform rollout notes.",
        "sources": [
            {
                "document_id": "doc-123",
                "source_type": "jira",
                "title": "Rollout Notes",
                "excerpt": "Release checklist and dependencies",
                "score": 0.91,
            },
            {
                "document_id": "doc-456",
                "source_type": "pdf",
                "excerpt": "Fallback source without title",
                "score": 0.73,
            },
        ],
        "model": "gpt-4o",
    }

    with respx.mock(base_url="http://mock-rag-service") as respx_mock:
        respx_mock.post("/query").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        result = await connector.query_research("market trends")

    assert result == {
        "type": "rag",
        "answer": "Use the latest AI platform rollout notes.",
        "sources": [
            {
                "name": "Rollout Notes",
                "document_id": "doc-123",
                "source_type": "jira",
                "title": "Rollout Notes",
                "excerpt": "Release checklist and dependencies",
                "score": 0.91,
            },
            {
                "name": "doc-456",
                "document_id": "doc-456",
                "source_type": "pdf",
                "excerpt": "Fallback source without title",
                "score": 0.73,
            },
        ],
        "model": "gpt-4o",
    }


@pytest.mark.asyncio
async def test_query_research_error_returns_rag_payload_shape():
    connector = RAGConnector(url="http://mock-rag-service")

    with respx.mock(base_url="http://mock-rag-service") as respx_mock:
        respx_mock.post("/query").mock(return_value=httpx.Response(500))

        result = await connector.query_research("fail")

    assert result["type"] == "rag"
    assert result["answer"] == ""
    assert result["sources"] == []
    assert "error" in result
