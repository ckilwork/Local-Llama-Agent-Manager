"""Persistent configuration for the single MVP llama-server instance."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ServerConfig:
    """User-editable llama-server launch settings."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "默认模板"
    server_path: str = ""
    model_path: str = ""
    mmproj_path: str = ""
    mtp_path: str = ""
    port: int = 8080
    context_length: int = 32768
    gpu_layers: int = -1
    flash_attention: bool = True
    jinja: bool = True
    reasoning_format: str = "auto"
    parallel: int = 1
    agent_profile: str = "gpt_oss_zh"
    system_prompt_scheme: str = ""
    system_prompt: str = (
        "你是一个运行在本地 llama.cpp server 上的中文 AI Agent。\n"
        "你不是 ChatGPT。\n"
        "请始终使用中文回答。\n"
        "如果有工具，请正确调用工具。"
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServerConfig":
        defaults = cls()
        valid = {field: data[field] for field in defaults.to_dict() if field in data}
        if not valid.get("name"):
            valid["name"] = "默认模板"
        return cls(**valid)
