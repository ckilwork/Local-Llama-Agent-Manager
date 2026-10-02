import struct
from pathlib import Path
from app.services.gguf_metadata import GGUFMetadataReader

def test_reads_llama_context_length(tmp_path: Path) -> None:
    target = tmp_path / "model.gguf"
    key, value = b"llama.context_length", 131072
    target.write_bytes(b"GGUF" + struct.pack("<IQQ", 3, 0, 1) + struct.pack("<Q", len(key)) + key + struct.pack("<I", 4) + struct.pack("<I", value))
    assert GGUFMetadataReader.read_context_length(str(target)) == value
