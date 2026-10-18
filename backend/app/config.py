"""Application configuration, read from environment variables.

Values come from backend/.env in development. See .env.example for the
placeholders; never commit real credentials.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Path to the SQLite database file, relative to the backend directory
    # unless an absolute path is given.
    database_path: str = Field(default="cafe.db")

    @property
    def database_file(self) -> Path:
        path = Path(self.database_path).expanduser()
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def database_url(self) -> str:
        return f"sqlite+pysqlite:///{self.database_file}"


settings = Settings()
