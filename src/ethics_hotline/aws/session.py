"""The one boto3 session the whole application shares.

The Comprehend, Textract, and S3 wrappers each take this session by
constructor injection rather than importing boto3 or calling
boto3.client() themselves. Nothing outside this module and the wrappers
imports boto3, and no route handler ever does.
"""

from __future__ import annotations

from functools import lru_cache

import boto3

from ethics_hotline.config import settings


@lru_cache(maxsize=1)
def get_session() -> boto3.Session:
    """Return the shared boto3 session, built once and reused.

    Region always comes from settings, Credentials are picked up by boto3's own default chain
    (the AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY environment
    variables) rather than being read or handled by this project's code.
    """
    return boto3.Session(region_name=settings.aws_region)