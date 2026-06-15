"""Unit tests for MockNewsConnector, RSSNewsConnector, and fallback news mode."""

from backend.connectors.news_connector import (
    LiveWithMockFallbackNewsConnector,
    MockNewsConnector,
    RSSNewsConnector,
)


# ---------------------------------------------------------------------------
# MockNewsConnector
# ---------------------------------------------------------------------------

class TestMockNewsConnector:
    def setup_method(self):
        self.connector = MockNewsConnector()

    def test_returns_list(self):
        items = self.connector.get_fx_news()
        assert isinstance(items, list)

    def test_default_max_items_is_5(self):
        items = self.connector.get_fx_news()
        assert len(items) <= 5

    def test_max_items_respected(self):
        items = self.connector.get_fx_news(max_items=3)
        assert len(items) == 3

    def test_max_items_1(self):
        items = self.connector.get_fx_news(max_items=1)
        assert len(items) == 1

    def test_max_items_larger_than_store(self):
        items = self.connector.get_fx_news(max_items=100)
        assert len(items) == len(MockNewsConnector._MOCK_ITEMS)

    def test_item_schema(self):
        items = self.connector.get_fx_news(max_items=1)
        item = items[0]
        assert "title" in item
        assert "summary" in item
        assert "source" in item
        assert "published" in item
        assert "url" in item
        assert isinstance(item["title"], str)
        assert isinstance(item["summary"], str)

    def test_query_filter_match(self):
        items = self.connector.get_fx_news(query="Fed", max_items=10)
        assert len(items) >= 1
        for item in items:
            assert "fed" in item["title"].lower() or "fed" in item["summary"].lower()

    def test_query_filter_ecb(self):
        items = self.connector.get_fx_news(query="ECB", max_items=10)
        assert len(items) >= 1
        for item in items:
            assert "ecb" in item["title"].lower() or "ecb" in item["summary"].lower()

    def test_query_filter_no_match_returns_empty(self):
        items = self.connector.get_fx_news(query="XYZZY_NOMATCH_12345", max_items=10)
        assert items == []

    def test_query_is_case_insensitive(self):
        upper = self.connector.get_fx_news(query="EUR", max_items=10)
        lower = self.connector.get_fx_news(query="eur", max_items=10)
        assert upper == lower

    def test_store_has_at_least_8_items(self):
        assert len(MockNewsConnector._MOCK_ITEMS) >= 8

    def test_query_and_max_items_combined(self):
        # At least 2 Fed/inflation items exist; cap at 1
        items = self.connector.get_fx_news(query="inflation", max_items=1)
        assert len(items) <= 1


# ---------------------------------------------------------------------------
# RSSNewsConnector — unit tests using injected stub feeds (no network)
# ---------------------------------------------------------------------------

FAKE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test FX Feed</title>
    <item>
      <title>Dollar rises on strong jobs data</title>
      <description>The US dollar climbed after payrolls beat expectations.</description>
      <link>https://example.com/dollar-rises</link>
      <pubDate>Sat, 28 Mar 2026 14:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Euro weakens ahead of ECB meeting</title>
      <description>EUR/USD fell as traders await ECB rate decision.</description>
      <link>https://example.com/euro-weakens</link>
      <pubDate>Sat, 28 Mar 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>JPY hits 150 vs USD</title>
      <description>The yen slipped past 150 per dollar on BOJ inaction.</description>
      <link>https://example.com/jpy-150</link>
      <pubDate>Fri, 27 Mar 2026 08:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""


class TestRSSNewsConnector:
    """Tests for RSSNewsConnector using feedparser with a fake local feed URL."""

    def _connector_with_fake_feed(self, xml: str = FAKE_RSS_XML):
        """Return an RSSNewsConnector whose _fetch_feed is monkey-patched."""
        import feedparser
        connector = RSSNewsConnector(feed_urls=["fake://test"])

        def fake_fetch(url):
            parsed = feedparser.parse(xml)
            source_name = parsed.get("feed", {}).get("title") or url
            items = []
            for entry in parsed.get("entries", []):
                title = connector._clean_text(entry.get("title", ""))
                summary = connector._clean_text(
                    entry.get("summary") or entry.get("description", "")
                )
                pub_dt = connector._entry_published(entry)
                url_out = entry.get("link", "")
                if not title:
                    continue
                items.append({
                    "title": title,
                    "summary": summary[:300],
                    "source": source_name,
                    "published": pub_dt.isoformat(),
                    "url": url_out,
                    "_dt": pub_dt,
                })
            return items

        connector._fetch_feed = fake_fetch
        return connector

    def test_returns_list(self):
        c = self._connector_with_fake_feed()
        items = c.get_fx_news()
        assert isinstance(items, list)

    def test_max_items_respected(self):
        c = self._connector_with_fake_feed()
        items = c.get_fx_news(max_items=2)
        assert len(items) <= 2

    def test_items_have_required_keys(self):
        c = self._connector_with_fake_feed()
        items = c.get_fx_news(max_items=10)
        assert len(items) > 0
        for item in items:
            assert "title" in item
            assert "summary" in item
            assert "source" in item
            assert "published" in item
            assert "url" in item
            assert "_dt" not in item  # internal key must be stripped

    def test_items_sorted_newest_first(self):
        c = self._connector_with_fake_feed()
        items = c.get_fx_news(max_items=10)
        dates = [item["published"] for item in items]
        assert dates == sorted(dates, reverse=True)

    def test_query_filter(self):
        c = self._connector_with_fake_feed()
        items = c.get_fx_news(query="ECB", max_items=10)
        assert len(items) >= 1
        for item in items:
            assert "ecb" in item["title"].lower() or "ecb" in item["summary"].lower()

    def test_query_no_match_returns_empty(self):
        c = self._connector_with_fake_feed()
        items = c.get_fx_news(query="XYZZY_NOMATCH", max_items=10)
        assert items == []

    def test_deduplication(self):
        """Duplicate titles from multiple feeds should appear only once."""
        connector = RSSNewsConnector(feed_urls=["fake://1", "fake://2"])
        call_count = {"n": 0}

        def fake_fetch(url):
            call_count["n"] += 1
            import feedparser
            parsed = feedparser.parse(FAKE_RSS_XML)
            source_name = "Test Feed"
            items = []
            for entry in parsed.get("entries", []):
                title = connector._clean_text(entry.get("title", ""))
                summary = connector._clean_text(
                    entry.get("summary") or entry.get("description", "")
                )
                pub_dt = connector._entry_published(entry)
                items.append({
                    "title": title,
                    "summary": summary[:300],
                    "source": source_name,
                    "published": pub_dt.isoformat(),
                    "url": entry.get("link", ""),
                    "_dt": pub_dt,
                })
            return items

        connector._fetch_feed = fake_fetch
        items = connector.get_fx_news(max_items=100)
        titles = [i["title"] for i in items]
        assert len(titles) == len(set(titles)), "Duplicate titles found"

    def test_all_feeds_fail_returns_empty(self):
        connector = RSSNewsConnector(feed_urls=["fake://bad"])
        connector._fetch_feed = lambda url: []
        items = connector.get_fx_news()
        assert items == []


class StubNewsConnector:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def get_fx_news(self, query=None, max_items=5):
        self.calls.append({"query": query, "max_items": max_items})
        if self.error:
            raise self.error
        if self.responses:
            return self.responses.pop(0)
        return []


class TestLiveWithMockFallbackNewsConnector:
    def test_uses_live_feed_first_and_marks_live_source(self):
        live = StubNewsConnector(
            responses=[
                [
                    {
                        "title": "Euro rises after ECB comments",
                        "summary": "EUR/USD moved higher.",
                        "source": "Live Feed",
                        "published": "2026-06-15T08:00:00+00:00",
                        "url": "https://example.com/live",
                    }
                ]
            ]
        )
        mock = StubNewsConnector(responses=[[{"title": "Mock item"}]])
        connector = LiveWithMockFallbackNewsConnector(live_connector=live, mock_connector=mock)

        items = connector.get_fx_news(query="EUR/USD", max_items=5)

        assert items[0]["title"] == "Euro rises after ECB comments"
        assert items[0]["data_source"] == "live_rss"
        assert live.calls == [{"query": "EUR/USD", "max_items": 5}]
        assert mock.calls == []

    def test_broad_latest_fx_query_uses_general_live_feed_not_exact_phrase_filter(self):
        live = StubNewsConnector(
            responses=[
                [
                    {
                        "title": "Tech shares rise on earnings",
                        "summary": "Stocks moved higher.",
                        "source": "Live Feed",
                        "published": "2026-06-15T08:00:00+00:00",
                        "url": "https://example.com/stocks",
                    },
                    {
                        "title": "Dollar slips as risk appetite improves",
                        "summary": "Major currencies traded firmer.",
                        "source": "Live Feed",
                        "published": "2026-06-15T08:00:00+00:00",
                        "url": "https://example.com/live",
                    }
                ]
            ]
        )
        connector = LiveWithMockFallbackNewsConnector(
            live_connector=live,
            mock_connector=StubNewsConnector(),
        )

        items = connector.get_fx_news(query="latest FX market news", max_items=5)

        assert len(items) == 1
        assert items[0]["title"] == "Dollar slips as risk appetite improves"
        assert items[0]["data_source"] == "live_rss"
        assert live.calls == [{"query": None, "max_items": 5}]

    def test_falls_back_to_mock_when_live_returns_empty(self):
        live = StubNewsConnector(responses=[[]])
        mock = StubNewsConnector(
            responses=[
                [
                    {
                        "title": "Fed holds rates steady amid inflation uncertainty",
                        "summary": "Mock summary",
                        "source": "Mock Financial Times",
                    }
                ]
            ]
        )
        connector = LiveWithMockFallbackNewsConnector(live_connector=live, mock_connector=mock)

        items = connector.get_fx_news(query="latest FX market news", max_items=5)

        assert items[0]["title"] == "Fed holds rates steady amid inflation uncertainty"
        assert items[0]["data_source"] == "mock_fallback"
        assert items[0]["fallback_reason"] == "live_empty"
        assert mock.calls == [{"query": None, "max_items": 5}]

    def test_falls_back_to_mock_when_live_errors(self):
        live = StubNewsConnector(error=TimeoutError("rss timeout"))
        mock = StubNewsConnector(responses=[[{"title": "Fallback headline"}]])
        connector = LiveWithMockFallbackNewsConnector(live_connector=live, mock_connector=mock)

        items = connector.get_fx_news(query="Fed", max_items=3)

        assert items[0]["data_source"] == "mock_fallback"
        assert items[0]["fallback_reason"] == "live_error: TimeoutError"
        assert mock.calls == [{"query": "Fed", "max_items": 3}]
