"""Preflight checks used by build.bat before creating a Windows release."""
from __future__ import annotations
from pathlib import Path
from app.services.config_service import ConfigService

def main() -> int:
    try:
        import PySide6  # noqa: F401
        print("[OK] PySide6 is available")
    except ImportError:
        print("[FAIL] PySide6 is missing"); return 1
    presets, selected = ConfigService().load_presets()
    server_path = Path(presets[selected].server_path)
    print("[OK] llama-server path configured" if server_path.is_file() else "[WARN] llama-server path is not configured; first-run wizard will ask for it")
    config_dir = ConfigService().config_path.parent; log_dir = config_dir / "logs"
    config_dir.mkdir(parents=True, exist_ok=True); log_dir.mkdir(parents=True, exist_ok=True)
    release_root = Path("dist") / "Local-Llama-Agent-Manager"
    for name in ("config", "logs", "data"): (release_root / name).mkdir(parents=True, exist_ok=True)
    print(f"[OK] config directory: {config_dir}"); print(f"[OK] log directory: {log_dir}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
