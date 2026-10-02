from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from app.main_window import MainWindow
from app.models.server_config import ServerConfig
from app.services.config_service import ConfigService


def test_prompt_scheme_create_save_select_and_reopen(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    service = ConfigService(tmp_path / "presets.json")
    window = MainWindow(service)
    assert window.right_splitter.widget(0) is window.agent_group
    assert window.agent_group.layout().rowCount() == 4
    assert window.prompt_scheme_combo.currentData() == ""
    assert window.system_prompt.toPlainText() == ""

    window.system_prompt.setPlainText("First prompt")
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: ("Coding", True))
    window.new_prompt_scheme_button.click()
    assert window.prompt_scheme_combo.currentData() == "Coding"
    assert service.load_prompt_schemes() == {"Coding": "First prompt"}

    window.system_prompt.setPlainText("Updated prompt")
    window.save_prompt_scheme_button.click()
    assert service.load_prompt_schemes() == {"Coding": "Updated prompt"}

    window.prompt_scheme_combo.setCurrentIndex(0)
    assert window.system_prompt.toPlainText() == ""
    window.system_prompt.setPlainText("Temporary text")
    window.prompt_scheme_combo.setCurrentIndex(window.prompt_scheme_combo.findData("Coding"))
    assert window.system_prompt.toPlainText() == "Updated prompt"
    window.close()

    reopened = MainWindow(service)
    assert reopened.prompt_scheme_combo.currentData() == "Coding"
    assert reopened.system_prompt.toPlainText() == "Updated prompt"
    reopened.close()


def test_prompt_scheme_delete_confirms_and_preserves_saved_prompts(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    service = ConfigService(tmp_path / "presets.json")
    window = MainWindow(service)
    assert not window.delete_prompt_scheme_button.isEnabled()

    window.system_prompt.setPlainText("Shared prompt")
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: ("Coding", True))
    window.new_prompt_scheme_button.click()
    window.presets.append(ServerConfig(
        name="Other", system_prompt_scheme="Coding", system_prompt="Saved prompt"
    ))
    assert window.delete_prompt_scheme_button.isEnabled()

    monkeypatch.setattr(QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.No)
    window.delete_prompt_scheme_button.click()
    assert service.load_prompt_schemes() == {"Coding": "Shared prompt"}

    monkeypatch.setattr(QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.Yes)
    window.delete_prompt_scheme_button.click()
    assert service.load_prompt_schemes() == {}
    assert not window.delete_prompt_scheme_button.isEnabled()
    assert window.prompt_scheme_combo.currentData() == ""
    assert window.system_prompt.toPlainText() == ""
    assert all(not preset.system_prompt_scheme for preset in window.presets)
    assert window.presets[0].system_prompt == "Shared prompt"
    assert window.presets[1].system_prompt == "Saved prompt"
    window.close()


def test_unselected_scheme_stays_visually_empty_for_legacy_prompt(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    service = ConfigService(tmp_path / "presets.json")
    service.save_presets([ServerConfig(system_prompt="Legacy prompt")], 0)
    window = MainWindow(service)
    assert window.prompt_scheme_combo.currentData() == ""
    assert window.system_prompt.toPlainText() == ""
    window.close()
    assert service.load_presets()[0][0].system_prompt == "Legacy prompt"
