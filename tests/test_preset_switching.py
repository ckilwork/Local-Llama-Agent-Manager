from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.models.server_config import ServerConfig
from app.services.config_service import ConfigService


def test_switching_presets_loads_and_preserves_all_runtime_fields(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(ConfigService(tmp_path / "presets.json"))
    first = ServerConfig(name="Text", model_path="text.gguf", mmproj_path="", context_length=32768, gpu_layers=1, flash_attention=False, jinja=False, reasoning_format="none", parallel=1, agent_profile="custom", system_prompt_scheme="Text", system_prompt="text prompt")
    second = ServerConfig(name="Vision", model_path="vision.gguf", mmproj_path="vision-mmproj.gguf", mtp_path="mtp.gguf", context_length=131072, gpu_layers=99, flash_attention=True, jinja=True, reasoning_format="deepseek", parallel=2, agent_profile="gpt_oss_zh", system_prompt_scheme="Vision", system_prompt="vision prompt")
    window.prompt_schemes = {"Text": "text prompt", "Vision": "vision prompt"}
    window._refresh_prompt_scheme_combo("")
    window.presets, window.selected_index = [first, second], 0
    window._refresh_list(); window.preset_list.setCurrentRow(0); window._load(first)
    window.preset_list.setCurrentRow(1)
    assert not hasattr(window, "agent_profile")
    assert window._form_config().agent_profile == "gpt_oss_zh"
    assert window.name_edit.text() == "Vision"
    assert window.model_edit.text() == "vision.gguf"
    assert window.mmproj_edit.text() == "vision-mmproj.gguf"
    assert window.mtp_edit.text() == "mtp.gguf"
    assert window._context_value() == 131072
    assert window.gpu.value() == 99 and window.flash.isChecked() and window.jinja.isChecked()
    assert window.reasoning.currentText() == "deepseek" and window.parallel.value() == 2
    assert window.system_prompt.toPlainText() == "vision prompt"
    assert "--mmproj vision-mmproj.gguf" in window.preview.toPlainText()
    assert "--spec-type draft-mtp --model-draft mtp.gguf" in window.preview.toPlainText()
    assert window.token_speed_label.text() == "0.0 token/s"
    window.preset_list.setCurrentRow(0)
    assert window._form_config().agent_profile == "custom"
    assert window.mtp_edit.text() == ""
    assert "--model-draft" not in window.preview.toPlainText()
    window.close()


def test_deleting_a_preset_loads_the_remaining_form(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(ConfigService(tmp_path / "presets.json"))
    window.presets = [
        ServerConfig(name="First", model_path="first.gguf"),
        ServerConfig(name="Second", model_path="second.gguf"),
    ]
    window.selected_index = 0
    window._refresh_list()
    window.preset_list.setCurrentRow(0)
    window._load(window.presets[0])

    window._delete()

    assert window.name_edit.text() == "Second"
    assert window.model_edit.text() == "second.gguf"
    assert window.presets[0].model_path == "second.gguf"
    window.close()
