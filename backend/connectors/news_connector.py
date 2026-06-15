"""News connectors — abstract base, mock, and live RSS implementations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class NewsConnectorBase(ABC):
    """Contract for all news connector implementations."""

    @abstractmethod
    def get_fx_news(
        self, query: Optional[str] = None, max_items: int = 5
    ) -> list[dict]:
        """Return up to *max_items* news items, optionally filtered by *query*.

        Each item is a dict with keys:
            title     – headline string
            summary   – short body text
            source    – publication / feed name
            published – ISO-8601 datetime string (UTC)
            url       – article URL
        """
        ...


# ---------------------------------------------------------------------------
# Mock connector (deterministic, no network)
# ---------------------------------------------------------------------------

class MockNewsConnector(NewsConnectorBase):
    """Returns hardcoded realistic FX news items. Safe to use in tests."""

    _MOCK_ITEMS: list[dict] = [
        {
            "title": "Fed holds rates steady amid inflation uncertainty",
            "summary": "The Federal Reserve kept its benchmark rate unchanged, citing persistent "
                       "inflation pressures and a resilient labour market as reasons for caution.",
            "source": "Mock Financial Times",
            "published": "2026-03-28T14:00:00+00:00",
            "url": "https://example.com/news/fed-holds-rates",
        },
        {
            "title": "EUR/USD climbs as ECB signals possible rate cut delay",
            "summary": "The euro strengthened against the dollar after ECB officials hinted that "
                       "the first rate cut of the year may be pushed to Q3 2026.",
            "source": "Mock FX Street",
            "published": "2026-03-28T10:30:00+00:00",
            "url": "https://example.com/news/eurusd-ecb-delay",
        },
        {
            "title": "GBP/USD steady after UK CPI beats expectations",
            "summary": "Sterling held gains versus the dollar as UK consumer price inflation "
                       "came in above forecasts, reducing expectations of a near-term BoE cut.",
            "source": "Mock Reuters",
            "published": "2026-03-27T09:00:00+00:00",
            "url": "https://example.com/news/gbpusd-uk-cpi",
        },
        {
            "title": "BOJ keeps ultra-loose policy, yen weakens past 150",
            "summary": "The Bank of Japan maintained its yield curve control policy, sending "
                       "USD/JPY above the 150 level for the first time since late 2025.",
            "source": "Mock Nikkei",
            "published": "2026-03-27T03:00:00+00:00",
            "url": "https://example.com/news/boj-yen-weakens",
        },
        {
            "title": "Dollar index retreats on softer US jobs data",
            "summary": "The DXY slipped 0.4% after non-farm payrolls missed the consensus "
                       "estimate, raising speculation the Fed may cut earlier than expected.",
            "source": "Mock Bloomberg",
            "published": "2026-03-26T16:00:00+00:00",
            "url": "https://example.com/news/dxy-jobs-data",
        },
        {
            "title": "AUD/USD rallies on strong Chinese PMI figures",
            "summary": "The Australian dollar rose sharply after China's manufacturing PMI beat "
                       "expectations, boosting risk appetite and demand for commodity currencies.",
            "source": "Mock FX Street",
            "published": "2026-03-26T02:00:00+00:00",
            "url": "https://example.com/news/audusd-china-pmi",
        },
        {
            "title": "Inflation in eurozone falls to 2.1%, approaching ECB target",
            "summary": "Flash CPI data showed eurozone inflation easing to 2.1% in March, "
                       "fuelling debate about the pace of ECB rate reductions later in 2026.",
            "source": "Mock Financial Times",
            "published": "2026-03-25T11:00:00+00:00",
            "url": "https://example.com/news/eurozone-inflation",
        },
        {
            "title": "USD/CAD dips as oil prices rebound on supply cut extension",
            "summary": "The Canadian dollar gained ground after OPEC+ confirmed an extension of "
                       "production cuts, pushing crude oil higher and weighing on USD/CAD.",
            "source": "Mock Reuters",
            "published": "2026-03-25T08:00:00+00:00",
            "url": "https://example.com/news/usdcad-oil-rebound",
        },
    ]

    def get_fx_news(
        self, query: Optional[str] = None, max_items: int = 5
    ) -> list[dict]:
        items: list[dict] = self._MOCK_ITEMS
        if query:
            q = query.lower()
            items = [
                i
                for i in items
                if q in i["title"].lower() or q in i["summary"].lower()
            ]
        return items[:max_items]


def _is_broad_news_query(query: Optional[str]) -> bool:
    if not query:
        return False
    terms = ("fx", "foreign exchange", "currency", "currencies", "market", "news", "latest")
    lowered = query.lower()
    return any(term in lowered for term in terms)


def _annotate_items(
    items: list[dict],
    data_source: str,
    fallback_reason: Optional[str] = None,
) -> list[dict]:
    annotated = []
    for item in items:
        copy = dict(item)
        copy["data_source"] = data_source
        if fallback_reason:
            copy["fallback_reason"] = fallback_reason
        annotated.append(copy)
    return annotated


def _filter_fx_relevant_items(items: list[dict]) -> list[dict]:
    terms = (
        "fx",
        "forex",
        "foreign exchange",
        "currency",
        "currencies",
        "dollar",
        "euro",
        "yen",
        "sterling",
        "pound",
        "franc",
        "eur/usd",
        "gbp/usd",
        "usd/jpy",
        "fed",
        "ecb",
        "boj",
        "rates",
    )
    relevant = []
    for item in items:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        if any(term in text for term in terms):
            relevant.append(item)
    return relevant


class LiveWithMockFallbackNewsConnector(NewsConnectorBase):
    """Use live RSS first, then deterministic mock headlines when live data is unavailable."""

    def __init__(
        self,
        live_connector: Optional[NewsConnectorBase] = None,
        mock_connector: Optional[NewsConnectorBase] = None,
    ) -> None:
        self._live_connector = live_connector or RSSNewsConnector()
        self._mock_connector = mock_connector or MockNewsConnector()

    def get_fx_news(
        self, query: Optional[str] = None, max_items: int = 5
    ) -> list[dict]:
        live_query = None if _is_broad_news_query(query) else query
        fallback_query = None if _is_broad_news_query(query) else query
        try:
            live_items = self._live_connector.get_fx_news(
                query=live_query,
                max_items=max_items,
            )
        except Exception as exc:
            mock_items = self._mock_connector.get_fx_news(
                query=fallback_query,
                max_items=max_items,
            )
            return _annotate_items(
                mock_items,
                "mock_fallback",
                f"live_error: {type(exc).__name__}",
            )

        if live_items and _is_broad_news_query(query):
            live_items = _filter_fx_relevant_items(live_items)

        if live_items:
            return _annotate_items(live_items, "live_rss")

        mock_items = self._mock_connector.get_fx_news(
            query=fallback_query,
            max_items=max_items,
        )
        return _annotate_items(mock_items, "mock_fallback", "live_empty")


# ---------------------------------------------------------------------------
# Live RSS connector
# ---------------------------------------------------------------------------

FEED_URLS: list[str] = [
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://www.investing.com/rss/news_25.rss",
    "https://www.fxstreet.com/rss/news",
]


class RSSNewsConnector(NewsConnectorBase):
    """Fetches FX news from public RSS feeds using feedparser. No API key required."""

    def __init__(self, feed_urls: Optional[list[str]] = None) -> None:
        self._feed_urls = feed_urls if feed_urls is not None else FEED_URLS

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _entry_published(entry) -> datetime:
        """Return a UTC-aware datetime from an entry's published_parsed tuple."""
        try:
            t = entry.get("published_parsed") or entry.get("updated_parsed")
            if t:
                return datetime(*t[:6], tzinfo=timezone.utc)
        except Exception:
            pass
        return datetime(1970, 1, 1, tzinfo=timezone.utc)

    @staticmethod
    def _clean_text(text: str) -> str:
        """Strip basic HTML tags from feed text."""
        import re
        return re.sub(r"<[^>]+>", "", text or "").strip()

    def _fetch_feed(self, url: str) -> list[dict]:
        """Fetch a single RSS feed and return normalised item dicts."""
        import feedparser  # local import so missing dep only raises at call-time

        try:
            parsed = feedparser.parse(url)
        except Exception as exc:
            log.warning("RSSNewsConnector: failed to fetch %s — %s", url, exc)
            return []

        source_name = (
            parsed.get("feed", {}).get("title") or url
        )
        items: list[dict] = []
        for entry in parsed.get("entries", []):
            title = self._clean_text(entry.get("title", ""))
            summary = self._clean_text(
                entry.get("summary") or entry.get("description", "")
            )
            published_dt = self._entry_published(entry)
            url_out = entry.get("link", "")
            if not title:
                continue
            items.append(
                {
                    "title": title,
                    "summary": summary[:300],  # cap length
                    "source": source_name,
                    "published": published_dt.isoformat(),
                    "url": url_out,
                    "_dt": published_dt,  # internal sort key, stripped before return
                }
            )
        return items

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_fx_news(
        self, query: Optional[str] = None, max_items: int = 5
    ) -> list[dict]:
        all_items: list[dict] = []
        seen_titles: set[str] = set()

        for url in self._feed_urls:
            for item in self._fetch_feed(url):
                title_key = item["title"].lower()
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    all_items.append(item)

        if not all_items:
            log.warning("RSSNewsConnector: all feeds returned no items")
            return []

        # Optional keyword filter
        if query:
            q = query.lower()
            all_items = [
                i
                for i in all_items
                if q in i["title"].lower() or q in i["summary"].lower()
            ]

        # Sort newest-first and cap
        all_items.sort(key=lambda i: i["_dt"], reverse=True)
        result = all_items[:max_items]

        # Strip internal sort key before returning
        for item in result:
            item.pop("_dt", None)

        return result
