"""Runtime configuration, read from environment variables prefixed ``BOUGHTSAFE_``."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import __version__


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOUGHTSAFE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./boughtsafe.db"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    log_level: str = "INFO"

    # Build metadata, injected by CI / Docker build args.
    build_number: str = "dev"
    git_sha: str = "local"

    # Upstream feeds.
    openfda_api_key: str | None = None
    openfda_url: str = "https://api.fda.gov/food/enforcement.json"
    fsis_url: str = "https://www.fsis.usda.gov/fsis/api/recall/v/1"
    cpsc_url: str = "https://www.saferproducts.gov/RestWebServices/Recall"
    off_url: str = "https://world.openfoodfacts.org/api/v2/product"
    off_enabled: bool = True
    contact_url: str = "https://github.com/lobojoel2003/Boughtsafe"
    http_timeout: float = 60.0
    backfill_from_year: int = 2012

    # Sync loop.
    sync_interval_minutes: int = 60
    full_refresh_hours: int = 24 * 7

    # Matching.
    max_items_per_request: int = 2000
    name_match_min_score: int = 82
    name_match_min_weight: float = 12.0
    name_match_days_before_purchase: int = 120
    name_match_days_after_purchase: int = 730
    upc_match_max_age_days: int = 730
    catalog_refresh_seconds: int = 60

    # Web Push (VAPID). Generate keys with ``boughtsafe vapid-keys``.
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str = "https://github.com/lobojoel2003/Boughtsafe"

    @property
    def user_agent(self) -> str:
        return f"Boughtsafe/{__version__} (+{self.contact_url})"

    @property
    def push_enabled(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
