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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.connector = create_connector()
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

    return app


app = create_app()
