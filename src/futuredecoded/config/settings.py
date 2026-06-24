"""Centralised Pydantic settings — separate from aalaya_mani / am bots."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3]
    )

    gemini_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    github_models_token: str = ""
    github_models_model: str = "openai/gpt-4o-mini"
    github_models_base_url: str = "https://models.github.ai"

    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    youtube_client_secrets: Path = Field(
        default_factory=lambda: Path("config/futuredecoded_client_secrets.json")
    )
    youtube_token_file: Path = Field(
        default_factory=lambda: Path("config/futuredecoded_youtube_token.pickle")
    )
    youtube_token_base64: str = ""
    client_secrets_base64: str = ""

    x_bearer_token: str = ""
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""

    trend_score_threshold: int = 80
    trend_score_fallback_threshold: int = 50
    database_url: str = "sqlite:///database/futuredecoded.db"
    log_level: str = "INFO"
    dry_run: bool = False

    use_cinematic_renderer: bool = True
    cinematic_fallback_ken_burns: bool = True
    stock_video_provider: str = "pexels"

    @property
    def outputs_dir(self) -> Path:
        return self.base_dir / "outputs"

    @property
    def assets_dir(self) -> Path:
        return self.base_dir / "assets"

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / "logs"

    @property
    def cache_dir(self) -> Path:
        return self.base_dir / ".cache"

    def ensure_dirs(self) -> None:
        for directory in (
            self.outputs_dir,
            self.assets_dir,
            self.logs_dir,
            self.cache_dir,
            self.base_dir / "database",
            self.base_dir / "config",
        ):
            directory.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
