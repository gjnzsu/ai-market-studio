"""Unit tests for MockNewsConnector and RSSNewsConnector."""

import pytest
from backend.connectors.news_connector import MockNewsConnector, RSSNewsConnector


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
            from datetime import datetime, timezone
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
            from datetime import datetime, timezone
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
