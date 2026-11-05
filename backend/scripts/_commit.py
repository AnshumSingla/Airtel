"""Short commit id for evidence reports: git if available, else $GITHUB_SHA, else 'unknown'."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def short_commit(repo: Path) -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                             cwd=repo, timeout=10).stdout.strip()
        if out:
            return out
    except (OSError, subprocess.SubprocessError):
        pass
    sha = os.environ.get("GITHUB_SHA", "")
    return sha[:7] if sha else "unknown"


def run_kind() -> str:
    """How this report was produced, stated in the report itself."""
    if os.environ.get("CI") == "true":
        return "CI run (GitHub Actions)"
    return "local run, not CI"
