"""Minimal GGUF metadata reader used for context-length warnings."""
from __future__ import annotations

import struct
from pathlib import Path


class GGUFMetadataReader:
    _sizes = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 1}

    @classmethod
    def read_context_length(cls, path: str) -> int | None:
        try:
            with Path(path).open("rb") as stream:
                if stream.read(4) != b"GGUF": return None
                version = cls._u32(stream)
                if version not in (2, 3): return None
                cls._u64(stream); count = cls._u64(stream)
                values: dict[str, object] = {}
                for _ in range(count):
                    key = cls._string(stream); value_type = cls._u32(stream); value = cls._value(stream, value_type)
                    values[key] = value
                architecture = str(values.get("general.architecture", ""))
                for key in ("n_ctx_train", "llama.context_length", "general.context_length", f"{architecture}.context_length"):
                    value = values.get(key)
                    if isinstance(value, int) and value > 0: return value
        except (OSError, ValueError, struct.error):
            return None
        return None

    @staticmethod
    def _u32(stream) -> int: return struct.unpack("<I", stream.read(4))[0]
    @staticmethod
    def _u64(stream) -> int: return struct.unpack("<Q", stream.read(8))[0]
    @classmethod
    def _string(cls, stream) -> str: return stream.read(cls._u64(stream)).decode("utf-8", errors="replace")
    @classmethod
    def _value(cls, stream, kind: int):
        if kind == 8: return cls._string(stream)
        if kind == 9:
            item_type, length = cls._u32(stream), cls._u64(stream)
            for _ in range(length): cls._value(stream, item_type)
            return None
        size = cls._sizes.get(kind)
        if size is None: raise ValueError("unsupported GGUF metadata type")
        raw = stream.read(size)
        if kind in (0, 2, 4, 10): return int.from_bytes(raw, "little", signed=False)
        return None
