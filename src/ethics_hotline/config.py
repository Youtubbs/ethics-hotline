"""Application configuration.

Every setting the app reads from the process environment is defined here.
No other module should call 'os.environ' or 'os.getenv' directly; import
and use the module-level 'settings' instance instead.

AWS region and S3 bucket are optional. nothing before the AWS wrapper
modules exercises them, so the app still boots with no AWS account or
credentials in existence, exactly as it did before this file gained
them. A later update will add max upload size the same way.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# 5 MB. Textract's synchronous DetectDocumentText caps at 10 MB, so this
# leaves room while keeping a single upload small.
DEFAULT_MAX_EVIDENCE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    database_url: str
    env: str
    log_level: str
    aws_region: str
    aws_s3_bucket: Optional[str]
    max_evidence_bytes: int

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
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            aws_s3_bucket=os.getenv("AWS_S3_BUCKET") or None,
            max_evidence_bytes=int(
                os.getenv("MAX_EVIDENCE_BYTES") or DEFAULT_MAX_EVIDENCE_BYTES
            ),
        )


settings = Settings.from_env()
