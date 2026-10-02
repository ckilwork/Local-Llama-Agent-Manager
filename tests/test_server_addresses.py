from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.models.server_config import ServerConfig
from app.services.config_service import ConfigService
from app.services.server_manager import ServerState


def test_browser_and_api_addresses_follow_selected_or_active_port(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(ConfigService(tmp_path / "presets.json"))
    assert window.browser_address.text() == "http://127.0.0.1:8080/"
    assert window.api_address.text() == "http://127.0.0.1:8080/v1"

    window.port.setValue(9090)
    assert window.api_address.text() == "http://127.0.0.1:9090/v1"
    window.api_copy_button.click()
    assert app.clipboard().text() == window.api_address.text()
    assert window.api_copy_button.text() == "复制"

    window.server_manager._active_config = ServerConfig(port=8080)
    window.server_manager._state = ServerState.RUNNING
    window._update_state(ServerState.RUNNING)
    assert window.browser_address.text() == "http://127.0.0.1:8080/"
    assert window.api_address.text() == "http://127.0.0.1:8080/v1"
    window.browser_copy_button.click()
    assert app.clipboard().text() == window.browser_address.text()

    window.server_manager._active_config = None
    window.server_manager._state = ServerState.STOPPED
    window._update_state(ServerState.STOPPED)
    assert window.browser_address.text() == "http://127.0.0.1:9090/"
    window.en_radio.click()
    assert window.browser_address.text() == "http://127.0.0.1:9090/"
    assert window.api_address.text() == "http://127.0.0.1:9090/v1"
    assert window.api_copy_button.text() == "Copy"
    window.close()


def test_address_bar_stays_aligned_with_middle_column(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(ConfigService(tmp_path / "presets.json"))
    window.show()
    def assert_aligned() -> None:
        app.processEvents()
        app.processEvents()
        central = window.centralWidget()
        address_x = window.browser_label.mapTo(central, window.browser_label.rect().topLeft()).x()
        middle_x = window.middle_panel.mapTo(central, window.middle_panel.rect().topLeft()).x()
        assert address_x == middle_x

    assert_aligned()
    window.resize(1477, 1039)
    assert_aligned()
    window.main_splitter.moveSplitter(280, 1)
    assert_aligned()
    window.close()
