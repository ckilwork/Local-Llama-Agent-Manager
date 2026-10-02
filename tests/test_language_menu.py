from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.services.config_service import ConfigService


def test_language_is_selected_directly_on_main_window(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    service = ConfigService(tmp_path / "presets.json")
    window = MainWindow(service)
    window.model_edit.setText("edited-model.gguf")

    assert window.menuBar().actions() == []
    assert window.menuBar().isHidden()
    assert window.zh_radio.text() == "简体中文"
    assert window.en_radio.text() == "English"
    assert window.zh_radio.isChecked()

    window.en_radio.click()
    assert window.language == "en_US"
    assert window.en_radio.isChecked()
    assert window.model_edit.text() == "edited-model.gguf"
    assert service.load_language() == "en_US"
    window.close()
