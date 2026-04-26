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
    use_mock_connector: bool = False
    use_mock_news_connector: bool = True  # independent flag; defaults True for safety

    # Optional connectors
    fred_api_key: Optional[SecretStr] = None

    cors_origins: str = "*"
    max_historical_days: int = 7
    rag_service_url: str = "http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
