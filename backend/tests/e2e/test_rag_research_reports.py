"""E2E test for RAG research reports collection query."""
import pytest
from backend.connectors.rag_connector import RAGConnector


@pytest.mark.asyncio
async def test_query_research_reports_collection():
    """Test that document_type='research_report' maps to collection='research_reports'."""
    connector = RAGConnector(url="http://34.10.130.210")
    
    # Query with document_type="research_report"
    result = await connector.query_research(
        question="List all available documents",
        document_type="research_report"
    )
    
    # Verify response structure
    assert result["type"] == "rag"
    assert "sources" in result
    assert isinstance(result["sources"], list)
    
    # Should return documents from research_reports collection
    assert len(result["sources"]) > 0, "No documents found in research_reports collection"
    
    # Verify documents are PDFs
    for source in result["sources"]:
        assert "name" in source
        assert source["name"].endswith(".pdf"), f"Expected PDF, got: {source['name']}"


@pytest.mark.asyncio
async def test_query_research_reports_eur_usd():
    """Test querying research reports for specific currency pair."""
    connector = RAGConnector(url="http://34.10.130.210")
    
    result = await connector.query_research(
        question="EUR/USD outlook",
        document_type="research_report"
    )
    
    assert result["type"] == "rag"
    assert len(result["sources"]) > 0, "No EUR/USD research found"
    
    # Verify answer is not empty
    assert result.get("answer", "").strip() != ""


@pytest.mark.asyncio
async def test_query_default_collection():
    """Test that queries without document_type use default collection."""
    connector = RAGConnector(url="http://34.10.130.210")
    
    result = await connector.query_research(
        question="What is the exchange rate?",
        document_type=None
    )
    
    # Should still work but query default collection
    assert result["type"] == "rag"
    assert "sources" in result
