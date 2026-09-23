from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from app.utils.env import env_bool, env_float, env_int, env_str

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    discord_token: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_base_url: str = ""
    yolo_model_path: str = "models/default.pt"
    database_url: str = "sqlite:///data/database/gta_ai.db"
    max_video_size_mb: int = Field(default=100, ge=1)
    analysis_fps: float = Field(default=5.0, gt=0)
    max_concurrent_analyses: int = Field(default=1, ge=1)
    replay_channel_id: int | None = None
    replay_retention_minutes: int = Field(default=30, ge=1)
    delete_replay_after_send: bool = True
    developer_user_ids: list[int] = Field(default_factory=list)
    human_examples_top_k: int = Field(default=5, ge=1)
    log_level: str = "INFO"
    discord_upload_limit_mb: int = Field(default=25, ge=1)
    ai_timeout_seconds: float = Field(default=45.0, gt=0)
    ai_max_retries: int = Field(default=2, ge=0)
    data_dir: Path = ROOT_DIR / "data"
    temp_dir: Path = ROOT_DIR / "data" / "temp"
    database_dir: Path = ROOT_DIR / "data" / "database"
    models_dir: Path = ROOT_DIR / "models"

    @field_validator("developer_user_ids", mode="before")
    @classmethod
    def parse_developer_ids(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(item) for item in value]
        return [int(part.strip()) for part in str(value).split(",") if part.strip()]

    @field_validator("replay_channel_id", mode="before")
    @classmethod
    def parse_optional_int(cls, value: object) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    def is_developer(self, user_id: int) -> bool:
        return user_id in self.developer_user_ids

    def ensure_runtime_dirs(self) -> None:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.database_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(ROOT_DIR / ".env")
    settings = Settings(
        discord_token=env_str("DISCORD_TOKEN"),
        ai_api_key=env_str("AI_API_KEY"),
        ai_model=env_str("AI_MODEL"),
        ai_base_url=env_str("AI_BASE_URL"),
        yolo_model_path=env_str("YOLO_MODEL_PATH", "models/default.pt"),
        database_url=env_str("DATABASE_URL", "sqlite:///data/database/gta_ai.db"),
        max_video_size_mb=env_int("MAX_VIDEO_SIZE_MB", 100),
        analysis_fps=env_float("ANALYSIS_FPS", 5.0),
        max_concurrent_analyses=env_int("MAX_CONCURRENT_ANALYSES", 1),
        replay_channel_id=env_str("REPLAY_CHANNEL_ID") or None,
        replay_retention_minutes=env_int("REPLAY_RETENTION_MINUTES", 30),
        delete_replay_after_send=env_bool("DELETE_REPLAY_AFTER_SEND", True),
        developer_user_ids=env_str("DEVELOPER_USER_IDS"),
        human_examples_top_k=env_int("HUMAN_EXAMPLES_TOP_K", 5),
        log_level=env_str("LOG_LEVEL", "INFO") or "INFO",
        discord_upload_limit_mb=env_int("DISCORD_UPLOAD_LIMIT_MB", 25),
        ai_timeout_seconds=env_float("AI_TIMEOUT_SECONDS", 45.0),
        ai_max_retries=env_int("AI_MAX_RETRIES", 2),
    )
    settings.ensure_runtime_dirs()
    return settings


def reset_settings_cache() -> None:
    get_settings.cache_clear()
