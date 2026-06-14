from backend.mcp_servers.market_data_server import (
    SOURCE_NAME,
    get_fx_history,
    get_fx_spot,
    list_supported_currencies,
)


def test_mcp_market_data_spot_tool_returns_deterministic_pair_data():
    result = get_fx_spot("EUR/USD", date="2026-06-14")

    assert result["base"] == "EUR"
    assert result["target"] == "USD"
    assert isinstance(result["rate"], float)
    assert result["date"] == "2026-06-14"
    assert result["source"] == SOURCE_NAME


def test_mcp_market_data_spot_tool_accepts_compact_pair_notation():
    result = get_fx_spot("EURUSD", date="2026-06-14")

    assert result["pair"] == "EUR/USD"
    assert result["base"] == "EUR"
    assert result["target"] == "USD"


def test_mcp_market_data_history_tool_is_repeatable():
    first = get_fx_history("EUR/USD", "2026-06-10", "2026-06-12")
    second = get_fx_history("EUR/USD", "2026-06-10", "2026-06-12")

    assert first == second
    assert first["pair"] == "EUR/USD"
    assert list(first["rates"].keys()) == [
        "2026-06-10",
        "2026-06-11",
        "2026-06-12",
    ]
    assert all(isinstance(rate, float) for rate in first["rates"].values())
    assert first["source"] == SOURCE_NAME


def test_mcp_market_data_currency_discovery():
    currencies = list_supported_currencies()

    assert "USD" in currencies
    assert "EUR" in currencies
    assert "JPY" in currencies
