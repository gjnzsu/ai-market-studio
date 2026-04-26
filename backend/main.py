import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.router import router
# Temporarily disabled for Cloud Build deployment
# from ai_sre_observability import setup_observability

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def create_connector():
    if settings.use_mock_connector:
        from backend.connectors.mock_connector import MockConnector
        logger.info("Using MockConnector (USE_MOCK_CONNECTOR=true)")
        return MockConnector()
    else:
        from backend.connectors.exchangerate_host import ExchangeRateHostConnector
        logger.info("Using ExchangeRateHostConnector")
        return ExchangeRateHostConnector(
            api_key=settings.exchangerate_api_key.get_secret_value()
        )


def create_news_connector():
    if settings.use_mock_news_connector:
        from backend.connectors.news_connector import MockNewsConnector
        logger.info("Using MockNewsConnector (USE_MOCK_NEWS_CONNECTOR=true)")
        return MockNewsConnector()
    else:
        from backend.connectors.news_connector import RSSNewsConnector
        logger.info("Using RSSNewsConnector (live RSS feeds)")
        return RSSNewsConnector()


def create_fred_connector():
    """Create FRED connector if API key is available."""
    if not settings.fred_api_key:
        logger.warning("FRED_API_KEY not set, FRED connector will be unavailable")
        return None
    from backend.connectors.fred_connector import FREDConnector
    logger.info("Initializing FREDConnector")
    return FREDConnector(api_key=settings.fred_api_key.get_secret_value())


def create_rag_connector():
    """Create RAG connector - will fail gracefully if service is unavailable."""
    from backend.connectors.rag_connector import RAGConnector
    logger.info(f"Initializing RAGConnector (RAG_SERVICE_URL={settings.rag_service_url})")
    return RAGConnector(base_url=settings.rag_service_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize connectors
    if not getattr(app.state, 'connector', None):
        app.state.connector = create_connector()
    if not getattr(app.state, 'news_connector', None):
        app.state.news_connector = create_news_connector()
    if not getattr(app.state, 'fred_connector', None):
        app.state.fred_connector = create_fred_connector()
    if not getattr(app.state, 'rag_connector', None):
        app.state.rag_connector = create_rag_connector()

    # Initialize observability - temporarily disabled for Cloud Build
    # observability_url = os.getenv(
    #     "OBSERVABILITY_URL",
    #     "http://ai-sre-observability.default.svc.cluster.local:8080"
    # )
    #
    # try:
    #     setup_observability(
    #         service_name="ai-market-studio",
    #         observability_url=observability_url,
    #         batch_interval=5.0,
    #         timeout=5.0
    #     )
    #     logger.info(f"Observability initialized: {observability_url}")
    # except Exception as e:
    #     logger.warning(f"Failed to initialize observability: {e}")
    #     # Continue without observability - graceful degradation

    logger.info("AI Market Studio started.")
    yield
    logger.info("AI Market Studio shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Market Studio",
        description="FX market data chatbot API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS configuration for separate frontend service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    app.include_router(router, prefix="/api")

    return app


app = create_app()
