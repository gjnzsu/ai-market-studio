import pytest
from fastapi.testclient import TestClient
from backend.connectors.mock_connector import MockConnector


@pytest.fixture
def mock_connector():
    return MockConnector()


@pytest.fixture
def error_connector():
    return MockConnector(error_pairs={"EUR/USD"})


@pytest.fixture
def app_client(mock_connector):
    """FastAPI TestClient with MockConnector injected."""
    from backend.main import create_app
    app = create_app()
    app.state.connector = mock_connector
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
