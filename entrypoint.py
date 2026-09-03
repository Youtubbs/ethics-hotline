"""Container entrypoint: apply pending migrations, then serve the API."""

from __future__ import annotations

import os
import subprocess
import sys

from ethics_hotline.logging import configure_logging, get_logger


def main() -> None:
    """Run pending migrations if any exist, then exec the Flask server."""
    configure_logging()
    logger = get_logger(__name__)

    if os.path.isdir("migrations"):
        logger.info("applying_migrations")
        subprocess.run(["flask", "db", "upgrade"], check=True)
    else:
        logger.info("no_migrations_directory_skipping_upgrade")

    os.execvp("flask", ["flask", "run", "--host=0.0.0.0", "--port=8000"])


if __name__ == "__main__":
    sys.exit(main())
