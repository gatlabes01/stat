from __future__ import annotations

import os
from pathlib import Path

_PKG = Path(__file__).resolve().parent.parent


def project_root() -> Path:
    raw = os.environ.get("REPO_ROOT")
    return Path(raw) if raw else _PKG