from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    x_bearer_token: str = ""
    db_path: str = "data/bodegas.db"

    # Rate limiting para X API Free tier
    api_max_requests_per_day: int = 500
    api_users_per_request: int = 100

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent.parent


settings = Settings()
