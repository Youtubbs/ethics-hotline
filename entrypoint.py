"""Container entrypoint: apply pending migrations, then serve the API."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    """Run pending migrations if any exist, then exec the Flask server."""
    if os.path.isdir("migrations"):
        print("Applying database migrations...")
        subprocess.run(["flask", "db", "upgrade"], check=True)
    else:
        print("No migrations directory found yet; skipping flask db upgrade.")

    os.execvp("flask", ["flask", "run", "--host=0.0.0.0", "--port=8000"])


if __name__ == "__main__":
    sys.exit(main())
