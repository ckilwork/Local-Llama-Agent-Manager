"""Local JSON persistence for the MVP preset list."""

from __future__ import annotations

import json
from pathlib import Path

from app.models.server_config import ServerConfig


class ConfigService:
    """Read and write presets to an application-local JSON file."""

    def __init__(self, config_path: Path | None = None) -> None:
        default_path = Path.home() / "AppData" / "Local" / "LlamaCppLauncher" / "presets.json"
        self.config_path = config_path or default_path

    def load_presets(self) -> tuple[list[ServerConfig], int]:
        """Return presets and selected index, falling back safely on bad data."""
        if not self.config_path.exists():
            return [ServerConfig()], 0
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
            presets = [ServerConfig.from_dict(item) for item in payload.get("presets", [])]
            if not presets:
                presets = [ServerConfig()]
            selected_index = int(payload.get("selected_index", 0))
            selected_index = max(0, min(selected_index, len(presets) - 1))
            return presets, selected_index
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return [ServerConfig()], 0

    def load_language(self) -> str:
        """Load the preferred UI locale; Chinese is the stable default."""
        if not self.config_path.exists():
            return "zh_CN"
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
            language = payload.get("language", "zh_CN")
            return language if language in {"zh_CN", "en_US"} else "zh_CN"
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return "zh_CN"

    def load_prompt_schemes(self) -> dict[str, str]:
        """Load reusable system prompts independently of server presets."""
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {}
            schemes = payload.get("prompt_schemes", {})
            if not isinstance(schemes, dict):
                return {}
            return {
                name: prompt for name, prompt in schemes.items()
                if isinstance(name, str) and name.strip() and isinstance(prompt, str)
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def save_presets(
        self,
        presets: list[ServerConfig],
        selected_index: int,
        language: str = "zh_CN",
        prompt_schemes: dict[str, str] | None = None,
    ) -> None:
        """Atomically persist presets so an interrupted write keeps the old file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "presets": [preset.to_dict() for preset in presets],
            "selected_index": selected_index,
            "language": language,
            "prompt_schemes": prompt_schemes if prompt_schemes is not None else self.load_prompt_schemes(),
        }
        temporary_path = self.config_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary_path.replace(self.config_path)
