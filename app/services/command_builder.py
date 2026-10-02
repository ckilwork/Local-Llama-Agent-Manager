"""Translate a ServerConfig into arguments accepted by llama-server."""

from __future__ import annotations

from app.models.server_config import ServerConfig


class CommandBuilder:
    """Build argument lists for QProcess without shell quoting issues."""

    @staticmethod
    def build_arguments(config: ServerConfig) -> list[str]:
        args = [
            "-m", config.model_path,
            "-c", str(config.context_length),
            "--port", str(config.port),
            "--gpu-layers", str(config.gpu_layers),
            "--parallel", str(config.parallel),
            "--reasoning-format", config.reasoning_format,
        ]

        if config.mmproj_path:
            args.extend(["--mmproj", config.mmproj_path])

        args.extend(["--flash-attn", "on" if config.flash_attention else "off"])
        args.append("--jinja" if config.jinja else "--no-jinja")

        if config.mtp_path:
            args.extend(["--spec-type", "draft-mtp"])
            args.extend(["--model-draft", config.mtp_path])
        return args

    @classmethod
    def build_command_preview(cls, config: ServerConfig) -> str:
        """Return a copyable Windows command preview for the current config."""
        executable = cls._quote(config.server_path)
        return " ".join([executable, *(cls._quote(arg) for arg in cls.build_arguments(config))])

    @staticmethod
    def _quote(value: str) -> str:
        if not value or any(char.isspace() for char in value):
            return f'"{value}"'
        return value
