import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.router import router

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
    use_mock = settings.use_mock_news_connector or settings.use_mock_connector
    if use_mock:
        from backend.connectors.news_connector import MockNewsConnector
        logger.info("Using MockNewsConnector (USE_MOCK_NEWS_CONNECTOR=true or USE_MOCK_CONNECTOR=true)")
        return MockNewsConnector()
    else:
        from backend.connectors.news_connector import RSSNewsConnector
        logger.info("Using RSSNewsConnector (live RSS feeds)")
        return RSSNewsConnector()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not getattr(app.state, 'connector', None):
        app.state.connector = create_connector()
    if not getattr(app.state, 'news_connector', None):
        app.state.news_connector = create_news_connector()
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

    # CORS — restrict in production
    # TODO: lock down allow_origins before deployment (currently PoC shortcut)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["POST", "GET"],
        allow_headers=["Content-Type"],
    )

    app.include_router(router, prefix="/api")

    from pathlib import Path
    frontend_dir = Path(__file__).parent.parent / "frontend"
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


app = create_app()
