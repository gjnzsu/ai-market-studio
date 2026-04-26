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
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def collect_market_data(
    data_type: str,
    connector: Any,
    pairs: Optional[list[str]] = None,
    query: Optional[str] = None,
    max_items: int = 5,
    series_id: Optional[str] = None,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """Collect market data from the appropriate source.

    Args:
        data_type: Type of data to collect ("rates", "news", "fred", "rag")
        connector: Connector instance (type depends on data_type)
        pairs: Currency pairs for rates (e.g., ["EUR/USD", "GBP/USD"])
        query: Search query for news or RAG
        max_items: Maximum items to return for news
        series_id: FRED series ID for interest rates
        date: Specific date for rates or FRED data
        start_date: Start date for historical data
        end_date: End date for historical data

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
        return await _collect_rates(connector, pairs, date, start_date, end_date)
    elif data_type == "news":
        return _collect_news(connector, query, max_items)
    elif data_type == "fred":
        return await _collect_fred(connector, series_id, date, start_date, end_date)
    elif data_type == "rag":
        return await _collect_rag(connector, query)
    else:
        raise ValueError(
            f"Invalid data_type: {data_type}. "
            f"Must be one of: rates, news, fred, rag"
        )


async def _collect_rates(
    connector: Any,
    pairs: Optional[list[str]],
    date: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
) -> dict[str, Any]:
    """Collect FX rate data from MarketDataConnector.

    Args:
        connector: MarketDataConnector instance
        pairs: List of currency pairs (e.g., ["EUR/USD"])
        date: Specific date for spot rates
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
        # Spot or specific date rates
        else:
            for pair in pairs:
                base, target = pair.split("/")
                rate_data = await connector.get_exchange_rate(
                    base=base,
                    target=target,
                    date=date,
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
            "date": date,
            "start_date": start_date,
            "end_date": end_date,
        },
    }


def _collect_news(
    connector: Any,
    query: Optional[str],
    max_items: int,
) -> dict[str, Any]:
    """Collect news data from NewsConnectorBase.

    Args:
        connector: NewsConnectorBase instance
        query: Optional search query to filter news
        max_items: Maximum number of news items to return

    Returns:
        dict with data_type, source, data, and metadata
    """
    try:
        news_items = connector.get_fx_news(query=query, max_items=max_items)
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
            "max_items": max_items,
        },
    }


async def _collect_fred(
    connector: Any,
    series_id: Optional[str],
    date: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
) -> dict[str, Any]:
    """Collect FRED interest rate data from FREDConnector.

    Args:
        connector: FREDConnector instance
        series_id: FRED series ID (e.g., "DFF", "DGS10")
        date: Specific date for current rate
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
        # Current or specific date rate
        else:
            rate_data = await connector.get_current_rate(
                series_id=series_id,
                date=date,
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
            "date": date,
            "start_date": start_date,
            "end_date": end_date,
        },
    }


async def _collect_rag(
    connector: Any,
    query: Optional[str],
) -> dict[str, Any]:
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
