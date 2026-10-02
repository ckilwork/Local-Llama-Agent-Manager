from pathlib import Path

from app.models.server_config import ServerConfig
from app.services.config_service import ConfigService


def test_config_service_round_trips_presets(tmp_path: Path) -> None:
    service = ConfigService(tmp_path / "presets.json")
    expected = [ServerConfig(name="Coding", port=8081), ServerConfig(name="Agent", port=8082, mtp_path="draft.gguf")]

    service.save_presets(expected, selected_index=1, language="en_US")
    actual, selected_index = service.load_presets()

    assert [item.to_dict() for item in actual] == [item.to_dict() for item in expected]
    assert selected_index == 1
    assert service.load_language() == "en_US"


def test_old_preset_without_new_agent_fields_remains_compatible() -> None:
    old_data = {"name": "Old", "model_path": "model.gguf", "context_length": 131072}
    preset = ServerConfig.from_dict(old_data)
    assert preset.context_length == 131072
    assert preset.agent_profile == "gpt_oss_zh"
    assert preset.mtp_path == ""
    assert preset.system_prompt_scheme == ""


def test_prompt_schemes_round_trip_without_changing_presets(tmp_path: Path) -> None:
    service = ConfigService(tmp_path / "presets.json")
    preset = ServerConfig(name="Agent", system_prompt="Original")
    service.save_presets([preset], 0, prompt_schemes={"Coding": "Code carefully"})
    assert service.load_prompt_schemes() == {"Coding": "Code carefully"}

    service.save_presets([preset], 0)
    assert service.load_prompt_schemes() == {"Coding": "Code carefully"}
    assert service.load_presets()[0][0].system_prompt == "Original"
