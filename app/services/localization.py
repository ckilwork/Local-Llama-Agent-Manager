"""JSON-backed local UI translation support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Translator:
    """Resolves dot-separated translation keys from a selected locale file."""

    def __init__(self, locale: str = "zh_CN") -> None:
        self.locale = locale
        self._messages: dict[str, Any] = {}
        self.load(locale)

    def load(self, locale: str) -> None:
        locale_path = Path(__file__).resolve().parents[2] / "resources" / "locales" / f"{locale}.json"
        self._messages = json.loads(locale_path.read_text(encoding="utf-8"))
        self.locale = locale

    def text(self, key: str, **values: object) -> str:
        current: Any = self._messages
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return key
            current = current[part]
        return str(current).format(**values)
