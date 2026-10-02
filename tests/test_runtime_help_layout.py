from PySide6.QtWidgets import QApplication, QLabel

from app.main_window import MainWindow
from app.services.config_service import ConfigService


def test_runtime_options_show_help_and_log_has_group_frame(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(ConfigService(tmp_path / "presets.json"))

    labels = [label.text() for label in window.findChildren(QLabel)]
    assert "加速注意力计算，通常更省显存；不兼容时关闭。" in labels
    assert "按模型聊天模板格式化请求，工具调用通常需要开启。" in labels
    assert window.flash.toolTip() in labels
    assert window.jinja.toolTip() in labels
    assert window.right_splitter.widget(1) is window.log_group
    assert window.log_group.title() == "运行日志"

    window.en_radio.click()
    labels = [label.text() for label in window.findChildren(QLabel)]
    assert "Speeds up attention and often saves VRAM; disable if incompatible." in labels
    assert window.log_group.title() == "Server Log"
    window.close()


def test_context_warning_row_only_takes_space_when_needed(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(ConfigService(tmp_path / "presets.json"))
    assert not window.runtime_form.isRowVisible(window.context_warning)

    window.model_context_length = 8192
    window._context_changed()
    assert window.runtime_form.isRowVisible(window.context_warning)
    assert "8K" in window.context_warning.text()

    window.model_context_length = 131072
    window._context_changed()
    assert not window.runtime_form.isRowVisible(window.context_warning)
    window.close()


def test_middle_and_right_columns_align_at_top_and_bottom(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(ConfigService(tmp_path / "presets.json"))
    window.resize(1180, 800)
    window.show()
    app.processEvents()

    middle = window.right_splitter.parentWidget().widget(1)
    middle_layout = middle.layout()
    assert middle_layout.itemAt(0).widget().geometry().top() == window.agent_group.geometry().top() == 0
    assert middle_layout.itemAt(2).widget().geometry().bottom() == middle.height() - 1
    assert window.log_group.geometry().bottom() == window.right_splitter.height() - 1
    window.close()
