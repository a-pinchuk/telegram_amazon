from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"
    admin_ids: list[int] = []
    timezone: str = "Europe/Kyiv"

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
