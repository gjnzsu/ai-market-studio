"""Data Collector Agent — unified data fetching from multiple sources.

Consolidates data retrieval from:
- FX rates (MarketDataConnector)
- News (NewsConnectorBase)
- FRED economic indicators (FREDConnector)
- RAG research documents (RAGConnector)

Routes requests by data_type and returns normalized payloads with metadata.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from backend.connectors.base import MarketDataConnector
from backend.connectors.news_connector import NewsConnectorBase
from backend.connectors.fred_connector import FREDConnector
from backend.connectors.rag_connector import RAGConnector

logger = logging.getLogger(__name__)


async def collect_market_data(
    data_type: Literal["rates", "news", "fred", "rag"],
    pairs: Optional[List[str]] = None,
    days: Optional[int] = None,
    series_id: Optional[str] = None,
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    connector: Optional[MarketDataConnector] = None,
    news_connector: Optional[NewsConnectorBase] = None,
    fred_connector: Optional[FREDConnector] = None,
    rag_connector: Optional[RAGConnector] = None,
) -> Dict[str, Any]:
    """Collect market data from the appropriate source.

    Args:
        data_type: Type of data to collect ("rates", "news", "fred", "rag")
        pairs: Currency pairs for rates (e.g., ["EUR/USD", "GBP/USD"])
        days: Number of days for historical data (alternative to start_date/end_date)
        series_id: FRED series ID for interest rates
        query: Search query for news or RAG
        start_date: Start date for historical data (YYYY-MM-DD)
        end_date: End date for historical data (YYYY-MM-DD)
        connector: MarketDataConnector instance for rates
        news_connector: NewsConnectorBase instance for news
        fred_connector: FREDConnector instance for FRED data
        rag_connector: RAGConnector instance for RAG data

    Returns:
        dict with keys:
            data_type: str
            source: str
            data: list or dict of results
            metadata: dict with timestamp, count, etc.

    Raises:
        ValueError: If data_type is invalid or required params missing
    """
    if data_type == "rates":
        if connector is None:
            raise ValueError("connector parameter is required for rates data_type")
        return await _collect_rates(connector, pairs, days, start_date, end_date)
    elif data_type == "news":
        if news_connector is None:
            raise ValueError("news_connector parameter is required for news data_type")
        return _collect_news(news_connector, query)
    elif data_type == "fred":
        if fred_connector is None:
            raise ValueError("fred_connector parameter is required for fred data_type")
        return await _collect_fred(fred_connector, series_id, days, start_date, end_date)
    elif data_type == "rag":
        if rag_connector is None:
            raise ValueError("rag_connector parameter is required for rag data_type")
        return await _collect_rag(rag_connector, query)
    else:
        raise ValueError(
            f"Invalid data_type: {data_type}. "
            f"Must be one of: rates, news, fred, rag"
        )


async def _collect_rates(
    connector: MarketDataConnector,
    pairs: Optional[List[str]],
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
) -> Dict[str, Any]:
    """Collect FX rate data from MarketDataConnector.

    Args:
        connector: MarketDataConnector instance
        pairs: List of currency pairs (e.g., ["EUR/USD"])
        days: Number of days for historical data
        start_date: Start date for historical rates
        end_date: End date for historical rates

    Returns:
        dict with data_type, source, data, and metadata
    """
    if not pairs:
        raise ValueError("pairs parameter is required for rates data_type")

    data = []
    source = "unknown"

    try:
        # Historical rates
        if start_date and end_date:
            for pair in pairs:
                base, target = pair.split("/")
                historical = await connector.get_historical_rates(
                    base=base,
                    targets=[target],
                    start_date=start_date,
                    end_date=end_date,
                )
                data.append({
                    "pair": pair,
                    "base": base,
                    "target": target,
                    "historical": historical,
                })
                source = "historical_rates"
        # Spot rates
        else:
            for pair in pairs:
                base, target = pair.split("/")
                rate_data = await connector.get_exchange_rate(
                    base=base,
                    target=target,
                    date=None,
                )
                data.append(rate_data)
                source = rate_data.get("source", "unknown")

    except Exception as e:
        logger.error(f"Error collecting rates data: {e}")
        raise

    return {
        "data_type": "rates",
        "source": source,
        "data": data,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count": len(data),
            "pairs": pairs,
            "days": days,
            "start_date": start_date,
            "end_date": end_date,
        },
    }


def _collect_news(
    connector: NewsConnectorBase,
    query: Optional[str],
) -> Dict[str, Any]:
    """Collect news data from NewsConnectorBase.

    Args:
        connector: NewsConnectorBase instance
        query: Optional search query to filter news

    Returns:
        dict with data_type, source, data, and metadata
    """
    try:
        news_items = connector.get_fx_news(query=query, max_items=5)
        source = news_items[0]["source"] if news_items else "news"

    except Exception as e:
        logger.error(f"Error collecting news data: {e}")
        raise

    return {
        "data_type": "news",
        "source": source,
        "data": news_items,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count": len(news_items),
            "query": query,
        },
    }


async def _collect_fred(
    connector: FREDConnector,
    series_id: Optional[str],
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
) -> Dict[str, Any]:
    """Collect FRED interest rate data from FREDConnector.

    Args:
        connector: FREDConnector instance
        series_id: FRED series ID (e.g., "DFF", "DGS10")
        days: Number of days for historical data
        start_date: Start date for historical rates
        end_date: End date for historical rates

    Returns:
        dict with data_type, source, data, and metadata
    """
    if not series_id:
        raise ValueError("series_id parameter is required for fred data_type")

    try:
        # Historical rates
        if start_date and end_date:
            historical_data = await connector.get_historical_rates(
                series_id=series_id,
                start_date=start_date,
                end_date=end_date,
            )
            data = historical_data.model_dump()
        # Current rate
        else:
            rate_data = await connector.get_current_rate(
                series_id=series_id,
                date=None,
            )
            data = rate_data.model_dump()

    except Exception as e:
        logger.error(f"Error collecting FRED data: {e}")
        raise

    return {
        "data_type": "fred",
        "source": "FRED",
        "data": data,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "series_id": series_id,
            "days": days,
            "start_date": start_date,
            "end_date": end_date,
        },
    }


async def _collect_rag(
    connector: RAGConnector,
    query: Optional[str],
) -> Dict[str, Any]:
    """Collect RAG research data from RAGConnector.

    Args:
        connector: RAGConnector instance
        query: Research question

    Returns:
        dict with data_type, source, data, and metadata
    """
    if not query:
        raise ValueError("query parameter is required for rag data_type")

    try:
        rag_result = await connector.query_research(question=query)

    except Exception as e:
        logger.error(f"Error collecting RAG data: {e}")
        raise

    return {
        "data_type": "rag",
        "source": "RAG",
        "data": rag_result,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "sources_count": len(rag_result.get("sources", [])),
        },
    }
