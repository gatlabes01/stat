from __future__ import annotations

import os
from pathlib import Path

_PKG = Path(__file__).resolve().parent.parent


def project_root() -> Path:
    raw = os.environ.get("REPO_ROOT")
    if raw:
        root = Path(raw).resolve()
        nested = root / "publisher"
        if (nested / "app").is_dir() and (nested / "templates").is_dir():
            return nested
        return root
    return _PKG