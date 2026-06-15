import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent.workflows import (
    analyze_market_context,
    collect_market_context,
    generate_market_briefing,
)
from backend.connectors.mock_connector import MockConnector


@pytest.mark.asyncio
async def test_collect_market_context_returns_data_only():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }

    result = await collect_market_context(
        pairs=["EUR/USD"],
        sources=["rates"],
        connector=connector,
    )

    assert result["type"] == "market_context"
    assert result["context"]["rates"][0]["rate"] == 1.08
    assert "analysis" not in result
    assert "briefing" not in result


@pytest.mark.asyncio
async def test_collect_market_context_includes_historical_rates_when_days_requested():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }
    connector.get_historical_rates.return_value = {
        "2026-05-18": {"USD": 1.07},
        "2026-05-19": {"USD": 1.08},
        "2026-05-20": {"USD": 1.09},
    }

    result = await collect_market_context(
        pairs=["EUR/USD"],
        sources=["rates"],
        days=3,
        connector=connector,
    )

    history = result["context"]["historical_rates"][0]
    assert history["pair"] == "EUR/USD"
    assert history["series"] == [
        {"date": "2026-05-18", "rate": 1.07},
        {"date": "2026-05-19", "rate": 1.08},
        {"date": "2026-05-20", "rate": 1.09},
    ]
    connector.get_historical_rates.assert_awaited_once()


@pytest.mark.asyncio
async def test_collect_market_context_falls_back_for_broad_fx_news_query():
    news_connector = MagicMock()
    news_connector.get_fx_news.side_effect = [
        [],
        [{"title": "Dollar index retreats", "source": "mock"}],
    ]

    result = await collect_market_context(
        sources=["news"],
        query="latest FX market news",
        news_connector=news_connector,
    )

    assert result["context"]["news"][0]["title"] == "Dollar index retreats"
    assert news_connector.get_fx_news.call_count == 2


@pytest.mark.asyncio
async def test_analyze_market_context_returns_analysis_not_briefing():
    context = {
        "type": "market_context",
        "context": {
            "rates": [
                {"date": "2026-05-19", "rate": 1.07},
                {"date": "2026-05-20", "rate": 1.08},
            ]
        },
        "warnings": [],
    }

    result = await analyze_market_context(
        context=context,
        analysis_type="trend",
    )

    assert result["type"] == "market_analysis"
    assert "analysis" in result
    assert "briefing" not in result


@pytest.mark.asyncio
async def test_analyze_market_context_uses_historical_rates_for_pair_specific_output():
    context = {
        "type": "market_context",
        "context": {
            "rates": [{"base": "EUR", "target": "USD", "rate": 1.09}],
            "historical_rates": [
                {
                    "pair": "EUR/USD",
                    "base": "EUR",
                    "target": "USD",
                    "start_date": "2026-05-18",
                    "end_date": "2026-05-20",
                    "series": [
                        {"date": "2026-05-18", "rate": 1.07},
                        {"date": "2026-05-19", "rate": 1.08},
                        {"date": "2026-05-20", "rate": 1.09},
                    ],
                }
            ],
        },
        "warnings": [],
    }

    result = await analyze_market_context(
        context=context,
        analysis_type="trend",
    )

    assert result["type"] == "market_analysis"
    assert result["analysis"]["pairs"][0]["pair"] == "EUR/USD"
    assert result["analysis"]["pairs"][0]["observations"] == 3


@pytest.mark.asyncio
async def test_analyze_market_context_recollects_when_supplied_context_is_malformed():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.09,
        "date": "2026-05-20",
        "source": "mock",
    }
    connector.get_historical_rates.return_value = {
        "2026-05-18": {"USD": 1.07},
        "2026-05-19": {"USD": 1.08},
        "2026-05-20": {"USD": 1.09},
    }

    result = await analyze_market_context(
        context={"rates": ["EUR/USD: 1.09"], "historical_series": []},
        pairs=["EUR/USD"],
        analysis_type="trend",
        days=3,
        connector=connector,
    )

    assert result["analysis"]["pairs"][0]["pair"] == "EUR/USD"
    connector.get_historical_rates.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_market_context_general_uses_trend_analysis():
    context = {
        "type": "market_context",
        "context": {
            "rates": [
                {"date": "2026-05-19", "rate": 1.07},
                {"date": "2026-05-20", "rate": 1.08},
            ]
        },
        "warnings": [],
    }

    result = await analyze_market_context(
        context=context,
        analysis_type="general",
    )

    assert result["type"] == "market_analysis"
    assert result["analysis"]["analysis_type"] == "trend"


@pytest.mark.asyncio
async def test_generate_market_briefing_coordinates_context_and_analysis():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }
    news_connector = MagicMock()
    news_connector.get_fx_news.return_value = []

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        connector=connector,
        news_connector=news_connector,
        include_research=False,
    )

    assert result["type"] == "market_briefing"
    assert "context" in result
    assert "analysis" in result
    assert "briefing" in result


@pytest.mark.asyncio
async def test_generate_market_briefing_normalizes_compact_pairs_and_warns_on_unsupported():
    result = await generate_market_briefing(
        pairs=["EURUSD", "USDCNH"],
        connector=MockConnector(),
        include_news=False,
        include_fred=False,
        include_research=False,
    )

    assert result["type"] == "market_briefing"
    assert result["context"]["context"]["rates"][0]["base"] == "EUR"
    assert result["context"]["context"]["rates"][0]["target"] == "USD"
    assert any("USD/CNH" in warning["error"] for warning in result["warnings"])


@pytest.mark.asyncio
async def test_generate_market_briefing_includes_selected_playbook_metadata():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        playbook="macro_rates",
        connector=connector,
        include_news=False,
        include_fred=False,
        include_research=False,
    )

    assert result["playbook"]["id"] == "macro_rates"
    assert result["playbook"]["display_name"] == "Macro-Rates Monitor"
    assert "fred" in result["playbook"]["required_sources"]
    assert "yield_curve_snapshot" in result["playbook"]["output_sections"]


@pytest.mark.asyncio
async def test_generate_market_briefing_represents_playbook_data_gaps():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        playbook="macro_rates",
        connector=connector,
        include_news=False,
        include_fred=False,
        include_research=False,
    )

    gap_sources = {gap["source"] for gap in result["data_gaps"]}
    assert {"breakevens", "swap_curve"} <= gap_sources
    assert all("not available" in gap["reason"] for gap in result["data_gaps"])


@pytest.mark.asyncio
async def test_fx_carry_briefing_includes_synthetic_specialist_data_and_metrics():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }
    fred_connector = AsyncMock()
    dff = MagicMock()
    dff.model_dump.return_value = {"series_id": "DFF", "value": 3.62}
    dgs10 = MagicMock()
    dgs10.model_dump.return_value = {"series_id": "DGS10", "value": 4.47}
    fred_connector.get_current_rate.side_effect = [dff, dgs10]

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        playbook="fx_carry",
        connector=connector,
        include_news=False,
        include_fred=True,
        fred_series_ids=["DFF", "DGS10"],
        fred_connector=fred_connector,
        include_research=False,
    )

    assert result["specialist_data"]["source"] == "synthetic"
    assert result["specialist_data"]["forward_curve"]["source"] == "synthetic"
    assert result["specialist_data"]["implied_volatility"]["source"] == "synthetic"
    assert result["carry_metrics"]["source"] == "synthetic"
    assert result["carry_metrics"]["rate_differential_proxy"] == 0.85
    assert result["carry_metrics"]["carry_to_vol"] == 0.12


@pytest.mark.asyncio
async def test_fx_carry_briefing_reports_synthetic_sources_separately():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        playbook="fx_carry",
        connector=connector,
        include_news=False,
        include_fred=False,
        include_research=False,
    )

    assert result["source_grounding"]["available_sources"] == ["rates"]
    assert result["source_grounding"]["synthetic_sources"] == [
        "forward_curve",
        "implied_volatility",
    ]


@pytest.mark.asyncio
async def test_fx_carry_briefing_does_not_gap_synthetic_specialist_data():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        playbook="fx_carry",
        connector=connector,
        include_news=False,
        include_fred=False,
        include_research=False,
    )

    gap_sources = {gap["source"] for gap in result["data_gaps"]}
    assert "forward_curve" not in gap_sources
    assert "implied_volatility" not in gap_sources


@pytest.mark.asyncio
async def test_generate_market_briefing_includes_source_grounding():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        playbook="morning_note",
        connector=connector,
        include_news=False,
        include_fred=False,
        include_research=False,
    )

    assert result["source_grounding"]["available_sources"] == ["rates"]
    assert "news" in result["source_grounding"]["requested_sources"]
    assert "news" in result["source_grounding"]["missing_required_sources"]
    assert "fred" in result["source_grounding"]["missing_optional_sources"]


@pytest.mark.asyncio
async def test_fx_carry_playbook_result_is_research_only():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        playbook="fx_carry",
        connector=connector,
        include_news=False,
        include_fred=False,
        include_research=False,
    )

    text = str(result).lower()
    assert result["playbook"]["research_only"] is True
    assert "research-only" in result["briefing"]["stance"].lower()
    assert "place order" not in text
    assert "execute trade" not in text


@pytest.mark.asyncio
async def test_market_briefing_represents_optional_research_failure():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.08,
        "date": "2026-05-20",
        "source": "mock",
    }
    rag = AsyncMock()
    rag.query_research.side_effect = Exception("RAG down")

    result = await generate_market_briefing(
        pairs=["EUR/USD"],
        connector=connector,
        include_news=False,
        include_fred=False,
        include_research=True,
        rag_connector=rag,
    )

    assert result["type"] == "market_briefing"
    assert any(w["source"] == "research" for w in result["warnings"])


@pytest.mark.asyncio
async def test_market_context_required_rate_failure_is_not_success():
    connector = AsyncMock()
    connector.get_exchange_rate.side_effect = Exception("rates down")

    with pytest.raises(Exception, match="rates down"):
        await collect_market_context(
            pairs=["EUR/USD"],
            sources=["rates"],
            connector=connector,
        )
