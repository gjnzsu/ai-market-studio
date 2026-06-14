from pydantic import SecretStr

from backend.config import Settings


def _settings(**overrides):
    values = {
        "openai_api_key": "test-openai",
        "exchangerate_api_key": "test-rates",
    }
    values.update(overrides)
    return Settings(**values)


def test_settings_accept_market_data_provider_selection():
    settings = _settings(
        market_data_provider="mcp",
        mcp_market_data_command="python",
        mcp_market_data_args="-m backend.mcp_servers.market_data_server",
        mcp_market_data_timeout_seconds=3.5,
    )

    assert settings.market_data_provider == "mcp"
    assert settings.mcp_market_data_command == "python"
    assert settings.mcp_market_data_args_list == [
        "-m",
        "backend.mcp_servers.market_data_server",
    ]
    assert settings.mcp_market_data_timeout_seconds == 3.5


def test_create_connector_uses_mcp_provider(monkeypatch):
    from backend import main
    from backend.connectors.mcp_market_data import MCPMarketDataConnector

    monkeypatch.setattr(main.settings, "market_data_provider", "mcp", raising=False)
    monkeypatch.setattr(main.settings, "mcp_market_data_command", "python", raising=False)
    monkeypatch.setattr(
        main.settings,
        "mcp_market_data_args",
        "-m backend.mcp_servers.market_data_server",
    )

    connector = main.create_connector()

    assert isinstance(connector, MCPMarketDataConnector)


def test_create_connector_preserves_mock_provider(monkeypatch):
    from backend import main
    from backend.connectors.mock_connector import MockConnector

    monkeypatch.setattr(main.settings, "market_data_provider", "mock", raising=False)
    monkeypatch.setattr(main.settings, "use_mock_connector", False)

    connector = main.create_connector()

    assert isinstance(connector, MockConnector)


def test_create_connector_preserves_exchangerate_host_provider(monkeypatch):
    from backend import main
    from backend.connectors.exchangerate_host import ExchangeRateHostConnector

    monkeypatch.setattr(
        main.settings,
        "market_data_provider",
        "exchangerate_host",
        raising=False,
    )
    monkeypatch.setattr(main.settings, "use_mock_connector", False)
    monkeypatch.setattr(main.settings, "exchangerate_api_key", SecretStr("key"))

    connector = main.create_connector()

    assert isinstance(connector, ExchangeRateHostConnector)
