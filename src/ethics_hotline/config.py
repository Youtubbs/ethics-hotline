"""Application configuration.

Every setting the app reads from the process environment is defined here.
No other module should call 'os.environ' or 'os.getenv' directly; import
and use the module-level 'settings' instance instead.

This module intentionally has no AWS fields yet. It is structured as a
plain dataclass with a single 'from_env' constructor so that later work
(AWS region, S3 bucket, max upload size) can add fields and matching
'os.getenv' calls in 'from_env' without changing how the rest of the
app consumes 'settings'.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    database_url: str
    env: str
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Build a 'Settings' instance from the current process environment."""
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is required")

        return cls(
            database_url=database_url,
            env=os.getenv("APP_ENV", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


settings = Settings.from_env()
