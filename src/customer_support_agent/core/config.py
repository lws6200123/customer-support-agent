"""Project paths, deterministic clocks, and environment-backed app settings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_OLIST_DIR = PROJECT_ROOT / "data" / "raw" / "olist"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
SEED_DATA_DIR = PROJECT_ROOT / "data" / "seed"
REPORTS_DIR = PROJECT_ROOT / "reports"
STAGE1_MANIFEST_PATH = REPORTS_DIR / "olist_raw_manifest.json"
DEMO_DATABASE_PATH = SEED_DATA_DIR / "customer_support_demo.db"

SIMULATION_NOW = datetime.fromisoformat("2026-09-03T12:00:00")
DEMO_RANDOM_SEED = 20260903
DEMO_ORDER_COUNT = 2_000

# Quotas are minimum coverage targets. Scenarios overlap, and the remaining
# capacity is deterministically filled from clean source orders.
SCENARIO_QUOTAS: tuple[tuple[str, int | None], ...] = (
    ("created", None),
    ("approved", None),
    ("shipped", 100),
    ("canceled", 100),
    ("unavailable", 100),
    ("invoiced", 80),
    ("processing", 80),
    ("delivered_late", 250),
    ("delivered_on_time", 500),
    ("low_review", 250),
    ("multi_item", 250),
    ("multi_payment", 200),
    ("source_chronology_anomaly", 10),
)


@dataclass(frozen=True)
class DemoBuildConfig:
    """Inputs that fully determine the generated demo dataset."""

    random_seed: int = DEMO_RANDOM_SEED
    target_order_count: int = DEMO_ORDER_COUNT
    simulation_now: datetime = SIMULATION_NOW
    scenario_quotas: tuple[tuple[str, int | None], ...] = SCENARIO_QUOTAS


class AppSettings(BaseSettings):
    """Runtime configuration; secrets remain wrapped and are never logged."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    cors_allowed_origins: str = "http://localhost:5173"
    database_path: Path = DEMO_DATABASE_PATH
    simulation_now: datetime = SIMULATION_NOW
    max_agent_steps: int = Field(default=8, ge=1, le=32)
    deepseek_base_url: str = ""
    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_model: str = ""
    deepseek_timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)
    deepseek_max_retries: int = Field(default=2, ge=0, le=5)
    llm_structured_output_attempts: int = Field(default=2, ge=1, le=3)
    ragflow_base_url: str = ""
    ragflow_api_key: SecretStr = SecretStr("")
    ragflow_dataset_id: str = ""
    ragflow_rerank_id: str | None = None
    ragflow_top_n: int = Field(default=5, ge=1, le=100)
    ragflow_similarity_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    ragflow_vector_similarity_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    ragflow_timeout_seconds: float = Field(default=10.0, gt=0.0, le=120.0)

    @property
    def ragflow_configured(self) -> bool:
        return bool(
            self.ragflow_base_url.strip()
            and self.ragflow_api_key.get_secret_value().strip()
            and self.ragflow_dataset_id.strip()
        )

    @property
    def deepseek_configured(self) -> bool:
        return bool(
            self.deepseek_base_url.strip()
            and self.deepseek_api_key.get_secret_value().strip()
            and self.deepseek_model.strip()
        )

    @property
    def cors_origins(self) -> list[str]:
        """Parse a comma-separated allowlist while explicitly rejecting wildcards."""
        origins = [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]
        return [origin for origin in origins if origin != "*"]
