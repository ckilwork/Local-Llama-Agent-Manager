"""First-run local file setup wizard."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWizard, QWizardPage
from app.services.localization import Translator

class FirstSetupWizard(QWizard):
    def __init__(self, translator: Translator, parent=None) -> None:
        super().__init__(parent); self.t = translator.text; self.setWindowTitle(self.t("setup.title")); self.server_path = ""; self.model_path = ""
        self.addPage(self._server_page()); self.addPage(self._model_page())
    def _server_page(self) -> QWizardPage:
        page = QWizardPage(); page.setTitle(self.t("setup.server_title")); layout = QVBoxLayout(page); layout.addWidget(QLabel(self.t("setup.server_message"))); edit = QLineEdit(); button = QPushButton(self.t("common.browse"))
        button.clicked.connect(lambda: edit.setText(QFileDialog.getOpenFileName(self, self.t("runtime.choose_server"), "", self.t("runtime.program_filter"))[0] or edit.text())); layout.addLayout(self._row(edit, button)); page.registerField("server*", edit); return page
    def _model_page(self) -> QWizardPage:
        page = QWizardPage(); page.setTitle(self.t("setup.model_title")); layout = QVBoxLayout(page); layout.addWidget(QLabel(self.t("setup.model_message"))); edit = QLineEdit(); button = QPushButton(self.t("common.browse"))
        button.clicked.connect(lambda: edit.setText(QFileDialog.getExistingDirectory(self, self.t("setup.choose_directory")) or edit.text())); layout.addLayout(self._row(edit, button)); page.registerField("model_dir*", edit); return page
    @staticmethod
    def _row(edit: QLineEdit, button: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout(); row.addWidget(edit); row.addWidget(button); return row
    def accept(self) -> None:
        server, model_dir = str(self.field("server")), Path(str(self.field("model_dir")))
        models = sorted(model_dir.rglob("*.gguf")) if model_dir.is_dir() else []
        if not models: return
        self.server_path, self.model_path = server, str(models[0]); super().accept()
