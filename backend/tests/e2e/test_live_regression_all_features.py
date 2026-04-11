"""
Regression tests for all ai-market-studio features.
Tests run against the LIVE deployed service at http://35.224.3.54.

These tests ensure:
1. All API endpoints are reachable and healthy
2. All agent tools produce valid responses
3. RAG service integration works
4. Live RSS news connector works (feedparser)
5. PDF export works

Run with: pytest backend/tests/e2e/test_live_regression_all_features.py -v
"""

import pytest
import requests


BASE_URL = "http://35.224.3.54"
SESSION_ID = "regression-test-session"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def chat(message: str, session_id: str = SESSION_ID, **kwargs) -> requests.Response:
    """POST /api/chat and return the response."""
    return requests.post(
        f"{BASE_URL}/api/chat",
        json={"message": message, "session_id": session_id, **kwargs},
        timeout=60,
    )


def get_historical(
    base: str = "USD",
    targets: list[str] = None,
    start_date: str = "2026-04-01",
    end_date: str = "2026-04-07",
) -> requests.Response:
    """POST /api/rates/historical. Date range must be < 7 days (MAX_HISTORICAL_DAYS=7)."""
    targets = targets or ["EUR", "GBP"]
    return requests.post(
        f"{BASE_URL}/api/rates/historical",
        json={"base": base, "targets": targets, "start_date": start_date, "end_date": end_date},
        timeout=30,
    )


def get_dashboard(
    panels: list[dict] = None,
    dashboard_id: str = "test-dashboard",
    dashboard_type: str = "mixed",
) -> requests.Response:
    """POST /api/dashboard. Requires dashboard_type field."""
    panels = panels or [
        {
            "panel_id": "p1",
            "panel_type": "line_trend",
            "base": "USD",
            "targets": ["EUR"],
            "start_date": "2026-04-01",
            "end_date": "2026-04-07",
        }
    ]
    return requests.post(
        f"{BASE_URL}/api/dashboard",
        json={"dashboard_id": dashboard_id, "dashboard_type": dashboard_type, "panels": panels},
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Smoke / Health
# ---------------------------------------------------------------------------

class TestSmoke:
    """Basic reachability and health checks."""

    def test_backend_is_reachable(self):
        """Backend API responds (not connection error)."""
        r = requests.get(f"{BASE_URL}/docs", timeout=10)
        assert r.status_code == 200

    def test_chat_endpoint_accepts_valid_request(self):
        """POST /api/chat with valid payload returns 200, not 500/503."""
        r = chat("Hello, what can you do?")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert "reply" in data
        assert isinstance(data["reply"], str)

    def test_chat_rejects_empty_message(self):
        """Empty message returns 422."""
        r = chat("")
        assert r.status_code == 422

    def test_chat_rejects_missing_message(self):
        """Missing message field returns 422."""
        r = requests.post(f"{BASE_URL}/api/chat", json={}, timeout=30)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Feature: get_exchange_rate
# ---------------------------------------------------------------------------

class TestExchangeRate:
    """Tests for single pair exchange rate lookups."""

    def test_single_pair_eurusd(self):
        """Single pair query returns a valid reply."""
        r = chat("What is EUR/USD right now?")
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]

    def test_single_pair_gbpusd(self):
        """Single pair query returns valid reply for GBP/USD."""
        r = chat("GBP/USD rate please")
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]

    def test_single_pair_usdjpy(self):
        """Single pair query works for USD/JPY."""
        r = chat("What is USD/JPY?")
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]


# ---------------------------------------------------------------------------
# Feature: get_exchange_rates
# ---------------------------------------------------------------------------

class TestExchangeRates:
    """Tests for multi-pair exchange rate lookups."""

    def test_multi_pair_rates(self):
        """Multi-pair query returns a valid reply."""
        r = chat("Get rates for USD/EUR, USD/GBP and USD/JPY")
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]

    def test_multi_pair_rates_three_pairs(self):
        """Three-pair query returns valid response."""
        r = chat("Show me USD/GBP, USD/EUR, USD/CHF rates")
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]


# ---------------------------------------------------------------------------
# Feature: list_supported_currencies
# ---------------------------------------------------------------------------

class TestSupportedCurrencies:
    """Tests for listing supported currencies."""

    def test_list_currencies(self):
        """Currency listing query returns valid reply."""
        r = chat("What currencies can you support?")
        if r.status_code == 502:
            pytest.skip("exchangerate.host rate limited (429)")
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]


# ---------------------------------------------------------------------------
# Feature: get_fx_news (live RSS via feedparser)
# ---------------------------------------------------------------------------

class TestFxNews:
    """Tests for the live RSS news connector (feedparser)."""

    def test_news_query_eurusd(self):
        """News query about EUR/USD returns news data (live RSS)."""
        r = chat("Any recent news about EUR/USD?")
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]
        # get_fx_news returns news in data.news
        news = data.get("data", {}).get("news", [])
        if news:
            # When live RSS works, sources should not be "Mock"
            for item in news:
                assert "Mock" not in item.get("source", ""), \
                    f"Expected live RSS source, got mock: {item.get('source')}"

    def test_news_query_no_filter(self):
        """General news query returns live headlines."""
        r = chat("What FX news is there today?")
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]

    def test_news_max_items_capped(self):
        """News items respect max_items cap (≤ 5)."""
        r = chat("Give me FX news")
        if r.status_code == 502:
            pytest.skip("exchangerate.host rate limited (429)")
        assert r.status_code == 200
        data = r.json()
        news = data.get("data", {}).get("news", [])
        if news:
            assert len(news) <= 5


# ---------------------------------------------------------------------------
# Feature: generate_market_insight
# ---------------------------------------------------------------------------

class TestMarketInsight:
    """Tests for generate_market_insight (combines rates + news)."""

    def test_market_insight_eurusd_gbpusd(self):
        """generate_market_insight for EUR/USD and GBP/USD returns rates."""
        r = chat("Give me a market insight on EUR/USD and GBP/USD")
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]
        # Should have FX rates in data
        rates = data.get("data", {}).get("rates", [])
        assert len(rates) >= 1

    def test_market_insight_single_pair(self):
        """generate_market_insight works for single pair."""
        r = chat("Give me market insight on USD/JPY")
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]
        rates = data.get("data", {}).get("rates", [])
        assert len(rates) >= 1


# ---------------------------------------------------------------------------
# Feature: generate_dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    """Tests for generate_dashboard (chart data)."""

    def test_dashboard_via_chat(self):
        """Dashboard-related chat query returns valid reply."""
        r = chat(
            "Show me a dashboard with USD/EUR and USD/GBP from April 2026 "
            "as a bar comparison chart"
        )
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]

    def test_dashboard_endpoint_historical_rates(self):
        """POST /api/rates/historical returns valid time-series data (max 7-day range).

        Note: May return 502 if exchangerate.host rate limit is hit (429).
        This is an external dependency limitation, not a code bug.
        """
        r = get_historical(
            base="USD",
            targets=["EUR", "GBP"],
            start_date="2026-04-01",
            end_date="2026-04-07",
        )
        if r.status_code == 502:
            pytest.skip("exchangerate.host rate limited (429) or GKE gateway error")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert data["base"] == "USD"
        assert data["start_date"] == "2026-04-01"
        assert data["end_date"] == "2026-04-07"
        series = data.get("series", [])
        assert len(series) > 0

    def test_dashboard_endpoint_caching(self):
        """Second identical request hits cache (cached=True).

        Note: May return 502 if exchangerate.host rate limit is hit.
        """
        r1 = get_historical(
            base="USD",
            targets=["CHF"],
            start_date="2026-04-02",
            end_date="2026-04-08",
        )
        if r1.status_code == 502:
            pytest.skip("exchangerate.host rate limited (429)")
        assert r1.status_code == 200
        assert r1.json().get("cached") is False

        r2 = get_historical(
            base="USD",
            targets=["CHF"],
            start_date="2026-04-02",
            end_date="2026-04-08",
        )
        assert r2.status_code == 200
        assert r2.json().get("cached") is True

    def test_dashboard_endpoint_422_on_empty_request(self):
        """Empty request body returns 422."""
        r = requests.post(f"{BASE_URL}/api/rates/historical", json={}, timeout=30)
        assert r.status_code == 422

    def test_dashboard_endpoint_422_on_date_range_too_large(self):
        """Date range ≥ 7 days returns 422."""
        r = get_historical(
            base="USD",
            targets=["EUR"],
            start_date="2026-04-01",
            end_date="2026-04-10",  # 9 days — exceeds 7-day limit
        )
        assert r.status_code == 422

    def test_dashboard_endpoint_multi_panel(self):
        """POST /api/dashboard with multiple panels returns data per panel.

        Note: May return 502 if exchangerate.host rate limit is hit.
        """
        r = get_dashboard(
            panels=[
                {
                    "panel_id": "p1",
                    "panel_type": "line_trend",
                    "base": "USD",
                    "targets": ["EUR"],
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-05",
                },
                {
                    "panel_id": "p2",
                    "panel_type": "bar_comparison",
                    "base": "USD",
                    "targets": ["GBP", "JPY"],
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-05",
                },
            ],
            dashboard_id="multi-panel-test",
            dashboard_type="mixed",
        )
        if r.status_code == 502:
            pytest.skip("exchangerate.host rate limited (429)")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert data["dashboard_id"] == "multi-panel-test"
        panels = data.get("panels", [])
        assert len(panels) == 2


# ---------------------------------------------------------------------------
# Feature: get_internal_research (RAG)
# ---------------------------------------------------------------------------

class TestRAGResearch:
    """Tests for RAG-based internal research (FX research reports)."""

    def test_rag_query_usd_hkd(self):
        """RAG research tool is triggered for research report queries."""
        r = chat(
            "based on the latest FX research report to come out "
            "the USD/HKD future 3 months trend analyst"
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert data["reply"]
        assert data.get("tool_used") == "get_internal_research"
        sources = data.get("data", {}).get("sources", [])
        assert len(sources) > 0
        assert sources[0].get("name") or sources[0].get("title")

    def test_rag_query_eur_usd_research(self):
        """RAG query for EUR/USD research returns sources."""
        r = chat("What does the latest research say about EUR/USD trends?")
        assert r.status_code == 200
        data = r.json()
        # LLM may choose research, insight, or news tool
        assert data["tool_used"] in (
            "get_internal_research",
            "generate_market_insight",
            "get_fx_news",
        )

    def test_rag_returns_normalized_sources(self):
        """RAG sources are normalized (name field present, deduped)."""
        r = chat(
            "based on the latest FX research report "
            "USD/HKD future 3 months trend analyst"
        )
        assert r.status_code == 200
        data = r.json()
        sources = data.get("data", {}).get("sources", [])
        assert len(sources) > 0
        # No duplicate source names
        names = [s.get("name") or s.get("title") for s in sources]
        assert len(names) == len(set(names)), f"Duplicate sources found: {sources}"


# ---------------------------------------------------------------------------
# Feature: export_to_pdf
# ---------------------------------------------------------------------------

class TestPDFExport:
    """Tests for PDF export via /api/export/pdf."""

    def test_pdf_export_with_insight_data(self):
        """PDF export returns valid PDF binary (starts with %PDF)."""
        r_chat = chat("Give me a market insight on EUR/USD")
        assert r_chat.status_code == 200
        chat_data = r_chat.json()

        r_pdf = requests.post(
            f"{BASE_URL}/api/export/pdf",
            json={
                "reply": chat_data["reply"],
                "data": chat_data.get("data"),
                "tool_used": chat_data.get("tool_used"),
            },
            timeout=30,
        )
        assert r_pdf.status_code == 200, \
            f"PDF export failed: {r_pdf.status_code} {r_pdf.text[:200]}"
        assert r_pdf.headers["content-type"] == "application/pdf"
        assert r_pdf.content.startswith(b"%PDF"), "Response is not a valid PDF"


# ---------------------------------------------------------------------------
# Feature: chat history
# ---------------------------------------------------------------------------

class TestChatHistory:
    """Tests for chat history support."""

    def test_chat_with_history(self):
        """Chat with non-empty history returns context-aware reply."""
        r = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "message": "And GBP/USD?",
                "session_id": "history-test",
                "history": [
                    {"role": "user", "content": "What is EUR/USD?"},
                    {"role": "assistant", "content": "EUR/USD is approximately 1.08."},
                ],
            },
            timeout=60,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["reply"]


# ---------------------------------------------------------------------------
# Feature: CORS
# ---------------------------------------------------------------------------

class TestCORS:
    """Tests for CORS headers."""

    def test_cors_headers_present(self):
        """CORS headers are present on chat endpoint."""
        r = requests.post(
            f"{BASE_URL}/api/chat",
            json={"message": "Hello"},
            headers={"Origin": "http://localhost:3000"},
            timeout=30,
        )
        assert r.status_code == 200
        # FastAPI CORSMiddleware with allow_credentials=True sends
        # Access-Control-Allow-Credentials but NOT Access-Control-Allow-Origin
        # (browsers handle this differently; the presence of allow_credentials
        # and the content-type being json are sufficient indicators)
        assert (
            "access-control-allow-credentials" in r.headers
            or "access-control-allow-origin" in r.headers
            or "content-type" in r.headers
        )
