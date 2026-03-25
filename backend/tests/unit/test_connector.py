import pytest
import respx
import httpx
from backend.connectors.exchangerate_host import ExchangeRateHostConnector
from backend.connectors.mock_connector import MockConnector
from backend.connectors.base import RateFetchError, UnsupportedPairError


# ---------------------------------------------------------------------------
# MockConnector tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_connector_direct_usd_pair():
    connector = MockConnector()
    result = await connector.get_exchange_rate("USD", "EUR")
    assert result["base"] == "USD"
    assert result["target"] == "EUR"
    assert isinstance(result["rate"], float)
    assert result["source"] == "mock"


@pytest.mark.asyncio
async def test_mock_connector_cross_rate_triangulation():
    connector = MockConnector()
    result = await connector.get_exchange_rate("EUR", "GBP")
    assert result["base"] == "EUR"
    assert result["target"] == "GBP"
    assert result["rate"] > 0


@pytest.mark.asyncio
async def test_mock_connector_same_currency():
    connector = MockConnector()
    result = await connector.get_exchange_rate("USD", "USD")
    assert result["rate"] == 1.0


@pytest.mark.asyncio
async def test_mock_connector_error_pairs():
    connector = MockConnector(error_pairs={"EUR/USD"})
    with pytest.raises(RateFetchError):
        await connector.get_exchange_rate("EUR", "USD")


@pytest.mark.asyncio
async def test_mock_connector_unsupported_pairs():
    connector = MockConnector(unsupported_pairs={"EUR/XYZ"})
    with pytest.raises(UnsupportedPairError):
        await connector.get_exchange_rate("EUR", "XYZ")


@pytest.mark.asyncio
async def test_mock_connector_get_exchange_rates():
    connector = MockConnector()
    results = await connector.get_exchange_rates("USD", ["EUR", "GBP", "JPY"])
    assert len(results) == 3
    assert all(r["base"] == "USD" for r in results)


@pytest.mark.asyncio
async def test_mock_connector_list_currencies():
    connector = MockConnector()
    currencies = await connector.list_supported_currencies()
    assert isinstance(currencies, list)
    assert "USD" in currencies
    assert "EUR" in currencies


@pytest.mark.asyncio
async def test_mock_connector_override_rate():
    connector = MockConnector(overrides={"USDEUR": 0.99})
    result = await connector.get_exchange_rate("USD", "EUR")
    assert result["rate"] == 0.99


# ---------------------------------------------------------------------------
# ExchangeRateHostConnector tests (respx mocks — no live HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exchangerate_host_happy_path(respx_mock):
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "quotes": {"USDGBP": 0.7856},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    result = await connector.get_exchange_rate("USD", "GBP")
    assert result["base"] == "USD"
    assert result["target"] == "GBP"
    assert result["rate"] == 0.7856
    assert result["source"] == "exchangerate.host"


@pytest.mark.asyncio
async def test_exchangerate_host_http_error(respx_mock):
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(500)
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    with pytest.raises(RateFetchError):
        await connector.get_exchange_rate("USD", "GBP")


@pytest.mark.asyncio
async def test_exchangerate_host_api_error_response(respx_mock):
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": False,
            "error": {"info": "Invalid API key"},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    with pytest.raises(RateFetchError, match="Invalid API key"):
        await connector.get_exchange_rate("USD", "GBP")


@pytest.mark.asyncio
async def test_exchangerate_host_missing_pair(respx_mock):
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "quotes": {},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    with pytest.raises(UnsupportedPairError):
        await connector.get_exchange_rate("USD", "XYZ")


@pytest.mark.asyncio
async def test_exchangerate_host_cross_rate_triangulation(respx_mock):
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "quotes": {"USDEUR": 0.92, "USDGBP": 0.786},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    result = await connector.get_exchange_rate("EUR", "GBP")
    assert result["base"] == "EUR"
    assert result["target"] == "GBP"
    expected = round(0.786 / 0.92, 6)
    assert result["rate"] == pytest.approx(expected)


@pytest.mark.asyncio
async def test_exchangerate_host_missing_api_key():
    with pytest.raises(RateFetchError):
        ExchangeRateHostConnector(api_key="")


# ---------------------------------------------------------------------------
# ExchangeRateHostConnector — get_exchange_rates (batched)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exchangerate_host_get_exchange_rates_usd_base(respx_mock):
    """Single API call returns all three pairs when base is USD."""
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "quotes": {"USDEUR": 0.92, "USDGBP": 0.786, "USDJPY": 149.5},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    results = await connector.get_exchange_rates("USD", ["EUR", "GBP", "JPY"])
    assert len(results) == 3
    assert results[0] == {"base": "USD", "target": "EUR", "rate": 0.92, "date": results[0]["date"], "source": "exchangerate.host"}
    assert results[1] == {"base": "USD", "target": "GBP", "rate": 0.786, "date": results[1]["date"], "source": "exchangerate.host"}
    assert results[2] == {"base": "USD", "target": "JPY", "rate": 149.5, "date": results[2]["date"], "source": "exchangerate.host"}


@pytest.mark.asyncio
async def test_exchangerate_host_get_exchange_rates_cross_base(respx_mock):
    """Non-USD base triggers triangulation for all targets in one call."""
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "quotes": {"USDEUR": 0.92, "USDGBP": 0.786, "USDJPY": 149.5},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    results = await connector.get_exchange_rates("EUR", ["GBP", "JPY"])
    assert len(results) == 2
    assert results[0]["base"] == "EUR"
    assert results[0]["target"] == "GBP"
    assert results[0]["rate"] == pytest.approx(round(0.786 / 0.92, 6))
    assert results[1]["base"] == "EUR"
    assert results[1]["target"] == "JPY"
    assert results[1]["rate"] == pytest.approx(round(149.5 / 0.92, 6))


@pytest.mark.asyncio
async def test_exchangerate_host_get_exchange_rates_same_currency(respx_mock):
    """Same base and target returns rate 1.0 without needing the quote key."""
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "quotes": {"USDEUR": 0.92},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    results = await connector.get_exchange_rates("USD", ["EUR", "USD"])
    usd_usd = next(r for r in results if r["target"] == "USD")
    assert usd_usd["rate"] == 1.0


@pytest.mark.asyncio
async def test_exchangerate_host_get_exchange_rates_missing_target(respx_mock):
    """Missing target currency in quotes raises UnsupportedPairError."""
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "quotes": {"USDEUR": 0.92},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    with pytest.raises(UnsupportedPairError):
        await connector.get_exchange_rates("USD", ["EUR", "XYZ"])


@pytest.mark.asyncio
async def test_exchangerate_host_get_exchange_rates_api_error(respx_mock):
    """API error response propagates as RateFetchError."""
    respx_mock.get("https://api.exchangerate.host/live").mock(
        return_value=httpx.Response(200, json={
            "success": False,
            "error": {"info": "Rate limit exceeded"},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    with pytest.raises(RateFetchError, match="Rate limit exceeded"):
        await connector.get_exchange_rates("USD", ["EUR", "GBP"])


# ---------------------------------------------------------------------------
# ExchangeRateHostConnector — list_supported_currencies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exchangerate_host_list_supported_currencies(respx_mock):
    respx_mock.get("https://api.exchangerate.host/list").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "currencies": {"USD": "US Dollar", "EUR": "Euro", "GBP": "British Pound"},
        })
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    currencies = await connector.list_supported_currencies()
    assert set(currencies) == {"USD", "EUR", "GBP"}


@pytest.mark.asyncio
async def test_exchangerate_host_list_supported_currencies_api_error(respx_mock):
    respx_mock.get("https://api.exchangerate.host/list").mock(
        return_value=httpx.Response(200, json={"success": False})
    )
    connector = ExchangeRateHostConnector(api_key="test_key")
    with pytest.raises(RateFetchError, match="Could not fetch currency list"):
        await connector.list_supported_currencies()
