from pathlib import Path
from typing import List
from urllib.parse import quote_plus

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")

    # Pre-built DATABASE_URL is optional — if absent, it is constructed from
    # the individual PG* variables that Railway resolves reliably.
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    database_sync_url: str | None = Field(default=None, alias="DATABASE_SYNC_URL")

    # Individual Postgres connection components (set by Railway's Postgres plugin)
    pghost: str | None = Field(default=None, alias="PGHOST")
    pgport: str = Field(default="5432", alias="PGPORT")
    pguser: str | None = Field(default=None, alias="PGUSER")
    pgpassword: str | None = Field(default=None, alias="PGPASSWORD")
    pgdatabase: str | None = Field(default=None, alias="PGDATABASE")

    admin_chat_ids: List[int] = Field(default_factory=list, alias="ADMIN_CHAT_IDS")
    premium_group_id: int = Field(alias="PREMIUM_GROUP_ID")
    premium_group_invite_link: str | None = Field(default=None, alias="PREMIUM_GROUP_INVITE_LINK")
    default_language: str = Field(default="en", alias="DEFAULT_LANGUAGE")
    upload_dir: str = Field(default="storage/uploads", alias="UPLOAD_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    webhook_host: str = Field(default="0.0.0.0", alias="WEBHOOK_HOST")
    webhook_port: int = Field(default=8080, alias="WEBHOOK_PORT")
    streamlit_port: int = Field(default=8501, alias="STREAMLIT_PORT")
    app_base_url: str = Field(default="http://localhost:8080", alias="APP_BASE_URL")
    trading_video_file_id: str | None = Field(default=None, alias="TRADING_VIDEO_FILE_ID")
    first_signal_text: str = Field(default="XAUUSD BUY, Entry: 2320.50, Stop Loss: 2315.00, Take Profit 1: 2325.00, Take Profit 2: 2330.00, Risk: 1.0%", alias="FIRST_SIGNAL_TEXT")

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        case_sensitive=False
    )

    @field_validator("admin_chat_ids", mode="before")
    @classmethod
    def parse_admin_chat_ids(cls, value):
        if value in (None, "", []):
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        text = str(value).strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        return [int(part.strip()) for part in text.split(",") if part.strip()]

    @model_validator(mode="after")
    def build_database_urls(self) -> "Settings":
        """
        If DATABASE_URL / DATABASE_SYNC_URL are missing or look like an
        unresolved Railway reference (contain '${'), build them from the
        individual PG* variables instead.
        """
        def _needs_build(url: str | None) -> bool:
            return not url or "${" in url

        if _needs_build(self.database_url) or _needs_build(self.database_sync_url):
            if not all([self.pghost, self.pguser, self.pgpassword, self.pgdatabase]):
                raise ValueError(
                    "DATABASE_URL is not set (or contains an unresolved reference) and "
                    "one or more of PGHOST, PGUSER, PGPASSWORD, PGDATABASE is also missing. "
                    "Please set either DATABASE_URL or all individual PG* variables."
                )
            password = quote_plus(self.pgpassword)  # type: ignore[arg-type]
            base = f"{self.pguser}:{password}@{self.pghost}:{self.pgport}/{self.pgdatabase}"
            if _needs_build(self.database_url):
                self.database_url = f"postgresql+asyncpg://{base}"
            if _needs_build(self.database_sync_url):
                self.database_sync_url = f"postgresql+psycopg2://{base}"

        return self

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    def ensure_dirs(self) -> None:
        self.upload_path.mkdir(parents=True, exist_ok=True)


settings = Settings()
