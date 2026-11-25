from __future__ import annotations

from app.paths import project_root

_CACHE: str | None = None

_FALLBACK = """Detailz voice: skeptical-but-fair, plain English, 0–2 signature hooks per article.
Hooks include: "We are definitely expecting this", "What is really going on over here?",
"Can we all just get along?", "Who made this nonsense happen?"
"""


def voice_samples_text() -> str:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    path = project_root() / "VOICE_SAMPLES.txt"
    if path.is_file():
        _CACHE = path.read_text(encoding="utf-8").strip()
    else:
        _CACHE = _FALLBACK
    return _CACHE


def voice_prompt_section() -> str:
    return voice_samples_text()