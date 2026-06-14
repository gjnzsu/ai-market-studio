import shlex
from typing import Optional
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    openai_api_key: SecretStr
    openai_model: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"

    exchangerate_api_key: SecretStr
    market_data_provider: str = "auto"
    use_mock_connector: bool = False
    use_mock_news_connector: bool = True  # independent flag; defaults True for safety
    mcp_market_data_command: str = "python"
    mcp_market_data_args: str = "-m backend.mcp_servers.market_data_server"
    mcp_market_data_timeout_seconds: float = 5.0

    # Optional connectors
    fred_api_key: Optional[SecretStr] = None

    cors_origins: str = "*"
    max_historical_days: int = 7
    rag_service_url: str = "http://localhost:8000"
    agent_timeout_seconds: float = 20.0
    agent_max_rounds: int = 2

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def mcp_market_data_args_list(self) -> list[str]:
        return shlex.split(self.mcp_market_data_args)


settings = Settings()
