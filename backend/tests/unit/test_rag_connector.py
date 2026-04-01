import pytest
import respx
import httpx
from backend.connectors.rag_connector import RAGConnector
from backend.config import settings

@pytest.mark.asyncio
async def test_query_research_success():
    connector = RAGConnector(url="http://mock-rag-service")
    mock_response = {"results": ["insight 1", "insight 2"]}

    with respx.mock(base_url="http://mock-rag-service") as respx_mock:
        respx_mock.post("/query").mock(return_value=httpx.Response(200, json=mock_response))

        result = await connector.query_research("market trends")
        assert result == mock_response

@pytest.mark.asyncio
async def test_query_research_error():
    connector = RAGConnector(url="http://mock-rag-service")

    with respx.mock(base_url="http://mock-rag-service") as respx_mock:
        respx_mock.post("/query").mock(return_value=httpx.Response(500))

        result = await connector.query_research("fail")
        assert "error" in result
