"""Test-container entrypoint that applies migrations, then runs the test suite.

A plain Python script, matching entrypoint.py, so nothing depends on a
shell being present the way it is on this Linux container versus however
the image was built.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    """Apply pending migrations against the test database, then run pytest."""
    subprocess.run(["flask", "db", "upgrade"], check=True)
    return subprocess.run(["pytest", "-q"]).returncode


if __name__ == "__main__":
    sys.exit(main())
