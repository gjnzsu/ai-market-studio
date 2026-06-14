import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent.workflows import (
    _split_pair,
    analyze_market_context,
    collect_market_context,
    generate_market_briefing,
)


def test_split_pair_accepts_compact_six_letter_fx_pair():
    assert _split_pair("eurusd") == ("EUR", "USD")


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
async def test_analyze_market_context_returns_fx_analysis_for_single_pair():
    context = {
        "type": "market_context",
        "context": {
            "rates": [
                {
                    "base": "EUR",
                    "target": "USD",
                    "date": "2026-05-19",
                    "rate": 1.07,
                    "source": "mock",
                },
                {
                    "base": "EUR",
                    "target": "USD",
                    "date": "2026-05-20",
                    "rate": 1.08,
                    "source": "mock",
                },
            ]
        },
        "warnings": [],
        "metadata": {"pairs": ["EUR/USD"], "sources": ["rates"], "days": 2},
    }

    result = await analyze_market_context(
        context=context,
        pairs=["EUR/USD"],
        analysis_type="fx_analysis",
        horizon="1w",
        focus="ECB vs Fed rate path",
    )

    assert result["type"] == "fx_analysis"
    assert result["pair"] == "EUR/USD"
    assert result["pairs"] == ["EUR/USD"]
    assert result["horizon"] == "1w"
    assert result["focus"] == "ECB vs Fed rate path"
    assert result["market_context_summary"]["primary_pair"] == "EUR/USD"
    assert result["sections"]["trend"]["direction"] == "higher"
    assert result["sections"]["momentum"]["latest_change"] == pytest.approx(0.01)
    assert result["sections"]["volatility"]["observation_count"] == 2
    assert {"bull", "base", "bear"} <= set(result["scenarios"])
    assert result["research_only"] is True


@pytest.mark.asyncio
async def test_analyze_market_context_labels_multi_pair_fx_analysis():
    context = {
        "type": "market_context",
        "context": {
            "rates": [
                {"base": "EUR", "target": "USD", "date": "2026-05-20", "rate": 1.08},
                {"base": "GBP", "target": "USD", "date": "2026-05-20", "rate": 1.27},
            ]
        },
        "warnings": [],
        "metadata": {"pairs": ["EURUSD", "GBP/USD"], "sources": ["rates"]},
    }

    result = await analyze_market_context(
        context=context,
        pairs=["EURUSD", "GBP/USD"],
        analysis_type="fx_analysis",
    )

    assert result["type"] == "fx_analysis"
    assert result["pair"] == "EUR/USD"
    assert result["pairs"] == ["EUR/USD", "GBP/USD"]
    assert [item["pair"] for item in result["pair_summaries"]] == [
        "EUR/USD",
        "GBP/USD",
    ]


@pytest.mark.asyncio
async def test_analyze_market_context_reports_grounding_gaps_and_confidence():
    context = {
        "type": "market_context",
        "context": {
            "rates": [
                {"base": "EUR", "target": "USD", "date": "2026-05-20", "rate": 1.08}
            ],
            "research": {
                "answer": "Internal research notes highlight softer USD momentum.",
                "sources": [{"title": "FX Weekly", "document_id": "doc-1"}],
            },
        },
        "warnings": [
            {"source": "news", "error": "News connector not available"},
            {"source": "fred", "error": "FRED connector not available"},
        ],
        "metadata": {"pairs": ["EUR/USD"], "sources": ["rates", "news", "fred", "research"]},
    }

    result = await analyze_market_context(
        context=context,
        pairs=["EUR/USD"],
        analysis_type="fx_analysis",
    )

    assert result["source_grounding"]["available_sources"] == ["rates", "research"]
    assert result["source_grounding"]["research_sources"] == ["FX Weekly"]
    gap_sources = {gap["source"] for gap in result["data_gaps"]}
    assert {"news", "fred", "history"} <= gap_sources
    assert result["confidence"]["score"] < 1
    assert result["confidence"]["label"] in {"low", "medium"}
    assert "research-only" in result["framing"].lower()
    text = str(result).lower()
    assert "place order" not in text
    assert "execute trade" not in text


@pytest.mark.asyncio
async def test_fx_analysis_can_be_grounded_in_mcp_sourced_spot_data():
    connector = AsyncMock()
    connector.get_exchange_rate.return_value = {
        "base": "EUR",
        "target": "USD",
        "rate": 1.0865,
        "date": "2026-06-14",
        "source": "mcp-mock-market-data",
    }

    result = await analyze_market_context(
        pairs=["EURUSD"],
        analysis_type="fx_analysis",
        connector=connector,
    )

    assert result["type"] == "fx_analysis"
    assert result["pair"] == "EUR/USD"
    assert result["market_context_summary"]["rate_sources"] == [
        "mcp-mock-market-data"
    ]
    assert result["source_grounding"]["rate_sources"] == ["mcp-mock-market-data"]
    assert result["research_only"] is True


@pytest.mark.asyncio
async def test_collect_market_context_uses_history_when_days_are_requested():
    connector = AsyncMock()
    connector.get_historical_rates.return_value = {
        "2026-06-12": {"USD": 1.08},
        "2026-06-13": {"USD": 1.081},
        "2026-06-14": {"USD": 1.086},
    }

    context = await collect_market_context(
        pairs=["EUR/USD"],
        sources=["rates"],
        days=3,
        connector=connector,
    )
    result = await analyze_market_context(
        context=context,
        pairs=["EUR/USD"],
        analysis_type="fx_analysis",
    )

    connector.get_historical_rates.assert_awaited_once()
    assert len(context["context"]["rates"]) == 3
    assert result["sections"]["trend"]["direction"] == "higher"
    assert result["sections"]["volatility"]["observation_count"] == 3
    assert "history" not in {gap["source"] for gap in result["data_gaps"]}


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
