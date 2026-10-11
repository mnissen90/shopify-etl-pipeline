"""Typed configuration loaded from environment variables.

All secrets, hosts, and paths come from the environment (see .env.example).
Nothing is hardcoded, so the same code runs locally and on the VM.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv is in requirements.txt; the project still works without it
    # as long as the variables are exported in the environment.
    pass

BASE_DIR = Path(__file__).resolve().parent
CLIENTS_DIR = Path(os.getenv("CLIENTS_DIR", BASE_DIR / "clients"))


def _get(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class DbConfig:
    server: str = field(default_factory=lambda: _get("DB_SERVER"))
    database: str = field(default_factory=lambda: _get("DB_NAME"))
    user: str = field(default_factory=lambda: _get("DB_USER"))
    password: str = field(default_factory=lambda: _get("DB_PASSWORD"))
    driver: str = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")

    @property
    def odbc_string(self) -> str:
        return (
            f"Driver={{{self.driver}}};"
            f"Server={self.server};"
            f"Database={self.database};"
            f"uid={self.user};"
            f"pwd={self.password}"
        )


@dataclass(frozen=True)
class ShopifyConfig:
    api_version: str = os.getenv("SHOPIFY_API_VERSION", "2020-10")


@dataclass(frozen=True)
class AlertConfig:
    sender: str = field(default_factory=lambda: _get("ALERT_FROM"))
    recipients: list[str] = field(
        default_factory=lambda: [
            r.strip() for r in _get("ALERT_TO").split(",") if r.strip()
        ]
    )
    smtp_host: str = field(default_factory=lambda: _get("SMTP_HOST"))
    smtp_port: int = _get_int("SMTP_PORT", 587)
    smtp_user: str = field(default_factory=lambda: _get("SMTP_USER"))
    smtp_password: str = field(default_factory=lambda: _get("SMTP_PASSWORD"))


@dataclass(frozen=True)
class PipelineConfig:
    overlap_days: int = _get_int("OVERLAP_DAYS", 10)
    max_retries: int = _get_int("MAX_RETRIES", 3)
    retry_backoff_seconds: int = _get_int("RETRY_BACKOFF_SECONDS", 20)
    clients_dir: Path = CLIENTS_DIR


@dataclass(frozen=True)
class Settings:
    db: DbConfig = field(default_factory=DbConfig)
    shopify: ShopifyConfig = field(default_factory=ShopifyConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
