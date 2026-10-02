"""Localized main window for the local llama-server manager."""
from __future__ import annotations

import uuid
from pathlib import Path
from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QRadioButton, QSizePolicy, QSpinBox, QInputDialog, QMenu,
    QSpacerItem, QSplitter, QVBoxLayout, QWidget)

from app.models.server_config import ServerConfig
from app.services.command_builder import CommandBuilder
from app.services.config_service import ConfigService
from app.services.localization import Translator
from app.services.gguf_metadata import GGUFMetadataReader
from app.widgets.first_setup_wizard import FirstSetupWizard
from app.services.server_manager import ServerManager, ServerState


class MainWindow(QMainWindow):
    def __init__(self, config_service: ConfigService | None = None) -> None:
        super().__init__()
        self.resize(1180, 800)
        self.config_service = config_service or ConfigService()
        self.language = self.config_service.load_language()
        self.translator = Translator(self.language)
        self.presets, self.selected_index = self.config_service.load_presets()
        self.prompt_schemes = self.config_service.load_prompt_schemes()
        self.server_manager = ServerManager(self.translator, self)
        self.model_context_length: int | None = None
        self._loading_preset = False
        self._build_window()

    def _t(self, key: str, **values: object) -> str: return self.translator.text(key, **values)

    def _build_window(self, logs: str = "") -> None:
        self.setWindowTitle(self._t("app_name")); self.menuBar().clear(); self.menuBar().hide(); self._build_ui(); self._bind_events()
        self._refresh_list(); self.preset_list.setCurrentRow(self.selected_index)
        self._load(self.presets[self.selected_index]); self._update_state(self.server_manager.state)
        self._update_token_speed(self.server_manager.token_speed)
        self.log_view.setPlainText(logs)

    def _build_ui(self) -> None:
        central = QWidget(self); self.setCentralWidget(central); root = QVBoxLayout(central)
        top_row = QHBoxLayout()
        top_row.setSpacing(0)
        self.address_leading_space = QSpacerItem(230, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        top_row.addItem(self.address_leading_space)
        addresses = QWidget()
        address_layout = QHBoxLayout(addresses)
        address_layout.setContentsMargins(0, 0, 0, 0)
        address_layout.setSpacing(6)
        self.browser_address = QLineEdit()
        self.api_address = QLineEdit()
        self.browser_copy_button = QPushButton(self._t("common.copy"))
        self.api_copy_button = QPushButton(self._t("common.copy"))
        for label_key, field, button in (
            ("server.browser_address", self.browser_address, self.browser_copy_button),
            ("server.api_address", self.api_address, self.api_copy_button),
        ):
            field.setReadOnly(True)
            label = QLabel(self._t(label_key))
            if field is self.browser_address:
                self.browser_label = label
            address_layout.addWidget(label)
            address_layout.addWidget(field, 1)
            address_layout.addWidget(button)
        addresses.setMaximumWidth(700)
        top_row.addWidget(addresses, 1)
        top_row.addStretch()
        top_row.addWidget(QLabel(self._t("common.language")))
        self.zh_radio = QRadioButton(self._t("common.simplified_chinese"))
        self.en_radio = QRadioButton(self._t("common.english"))
        language_group = QButtonGroup(central)
        language_group.addButton(self.zh_radio); language_group.addButton(self.en_radio)
        (self.zh_radio if self.language == "zh_CN" else self.en_radio).setChecked(True)
        self.zh_radio.toggled.connect(lambda checked: self._set_language("zh_CN") if checked else None)
        self.en_radio.toggled.connect(lambda checked: self._set_language("en_US") if checked else None)
        top_row.addWidget(self.zh_radio); top_row.addWidget(self.en_radio)
        root.addLayout(top_row)
        split = QSplitter(Qt.Horizontal); root.addWidget(split)
        self.main_splitter = split
        left = QWidget(); left_layout = QVBoxLayout(left); left_layout.addWidget(QLabel(self._t("preset.title")))
        self.preset_list = QListWidget(); self.preset_list.setContextMenuPolicy(Qt.CustomContextMenu); left_layout.addWidget(self.preset_list); grid = QGridLayout()
        self.new_button = QPushButton(self._t("preset.new")); self.delete_button = QPushButton(self._t("preset.delete")); self.save_button = QPushButton(self._t("common.save"))
        grid.addWidget(self.new_button, 0, 0); grid.addWidget(self.delete_button, 0, 1); grid.addWidget(self.save_button, 1, 0, 1, 2); left_layout.addLayout(grid); split.addWidget(left)
        middle = QWidget(); middle_layout = QVBoxLayout(middle)
        self.middle_panel = middle
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(10)
        middle_layout.addWidget(self._status_group())
        middle_layout.addWidget(self._runtime_group())
        middle_layout.addWidget(self._command_group(), 1)
        split.addWidget(middle)
        self.right_splitter = QSplitter(Qt.Vertical)
        self.agent_group = self._agent_group(); self.right_splitter.addWidget(self.agent_group)
        self.log_group = QGroupBox(self._t("log.title"))
        log_layout = QVBoxLayout(self.log_group)
        self.log_view = QPlainTextEdit(); self.log_view.setReadOnly(True); self.log_view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont)); log_layout.addWidget(self.log_view)
        self.clear_button = QPushButton(self._t("log.clear")); log_layout.addWidget(self.clear_button)
        self.right_splitter.addWidget(self.log_group)
        self.right_splitter.setStretchFactor(0, 0)
        self.right_splitter.setStretchFactor(1, 1)
        self.right_splitter.setSizes([290, 510])
        split.addWidget(self.right_splitter); split.setSizes([190, 570, 420])
        split.installEventFilter(self)
        split.splitterMoved.connect(self._sync_address_alignment)

    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:
        if watched is getattr(self, "main_splitter", None) and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self._sync_address_alignment)
        return super().eventFilter(watched, event)

    def _sync_address_alignment(self, *_: object) -> None:
        if not self.middle_panel.isVisible():
            return
        central = self.centralWidget()
        middle_x = self.middle_panel.mapTo(central, self.middle_panel.rect().topLeft()).x()
        label_x = self.browser_label.mapTo(central, self.browser_label.rect().topLeft()).x()
        current_width = self.address_leading_space.sizeHint().width()
        leading_width = max(0, current_width + middle_x - label_x)
        if current_width != leading_width:
            self.address_leading_space.changeSize(leading_width, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
            central.layout().invalidate()

    def _status_group(self) -> QGroupBox:
        group = QGroupBox(self._t("server.title"))
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 20, 14, 14)
        layout.setSpacing(14)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(18)
        self.status_label = QLabel()
        self.pid_label = QLabel("-")
        self.token_speed_label = QLabel()
        for column, (key, value) in enumerate((
            ("server.status", self.status_label),
            ("server.pid", self.pid_label),
            ("server.token_speed", self.token_speed_label),
        )):
            metrics.addWidget(QLabel(f"{self._t(key)}："), 0, column)
            metrics.addWidget(value, 1, column)
            metrics.setColumnStretch(column, 1)
        layout.addLayout(metrics)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.start_button = QPushButton(self._t("server.start"))
        self.stop_button = QPushButton(self._t("server.stop"))
        self.restart_button = QPushButton(self._t("server.restart"))
        for button in (self.start_button, self.stop_button, self.restart_button):
            button.setMinimumHeight(32)
            buttons.addWidget(button, 1)
        layout.addLayout(buttons)
        return group

    def _runtime_group(self) -> QGroupBox:
        group = QGroupBox(self._t("runtime.title")); form = QFormLayout(group)
        self.runtime_form = form
        self.name_edit = QLineEdit(); self.server_edit = QLineEdit(); self.model_edit = QLineEdit(); self.mmproj_edit = QLineEdit()
        self.mtp_edit = QLineEdit()
        form.addRow(self._t("preset.name"), self.name_edit)
        form.addRow(self._t("runtime.server_path"), self._with_button(self.server_edit, self._picker(self.server_edit, "runtime.choose_server", "runtime.program_filter")))
        form.addRow(self._t("runtime.model"), self._with_button(self.model_edit, self._picker(self.model_edit, "runtime.choose_model", "runtime.gguf_filter")))
        mmproj_box = QWidget(); mmproj_layout = QHBoxLayout(mmproj_box); mmproj_layout.setContentsMargins(0, 0, 0, 0)
        mmproj_box_button = self._picker(self.mmproj_edit, "runtime.choose_mmproj", "runtime.gguf_filter")
        mmproj_clear = QPushButton(self._t("runtime.clear")); mmproj_clear.clicked.connect(self.mmproj_edit.clear)
        mmproj_layout.addWidget(self.mmproj_edit); mmproj_layout.addWidget(mmproj_box_button); mmproj_layout.addWidget(mmproj_clear)
        form.addRow(self._t("runtime.mmproj"), mmproj_box)
        mtp_box = QWidget(); mtp_layout = QHBoxLayout(mtp_box); mtp_layout.setContentsMargins(0, 0, 0, 0)
        mtp_box_button = self._picker(self.mtp_edit, "runtime.choose_mtp", "runtime.gguf_filter")
        mtp_clear = QPushButton(self._t("runtime.clear")); mtp_clear.clicked.connect(self.mtp_edit.clear)
        mtp_layout.addWidget(self.mtp_edit); mtp_layout.addWidget(mtp_box_button); mtp_layout.addWidget(mtp_clear)
        form.addRow(self._t("runtime.mtp"), mtp_box)
        self.port = self._spin(1, 65535, 8080); self.context_combo = QComboBox(); self.context_custom = self._spin(1, 2_000_000, 32768); self.gpu = self._spin(-1, 9999, -1); self.parallel = self._spin(1, 128, 1)
        for label, value in (("8K",8192),("16K",16384),("32K",32768),("64K",65536),("128K",131072),("256K",262144),("512K",524288)): self.context_combo.addItem(label, value)
        self.context_combo.addItem(self._t("runtime.custom"), None); self.context_custom.setVisible(False)
        self.flash = QCheckBox(); self.jinja = QCheckBox(); self.reasoning = QComboBox(); self.reasoning.addItems(["auto", "none", "deepseek", "deepseek-legacy"])
        context_box = QWidget(); context_layout = QHBoxLayout(context_box); context_layout.setContentsMargins(0,0,0,0); context_layout.addWidget(self.context_combo); context_layout.addWidget(self.context_custom)
        form.addRow(self._t("runtime.port"), self.port); form.addRow(self._t("runtime.context"), context_box); self.context_warning = QLabel(); self.context_warning.setWordWrap(True); self.context_warning.setStyleSheet("color: #b26a00;"); form.addRow("", self.context_warning); form.setRowVisible(self.context_warning, False); form.addRow(f"{self._t('runtime.gpu_layers')} ({self._t('runtime.gpu_auto')})", self.gpu)
        form.addRow(self._t("runtime.flash_attention"), self._option_with_help(self.flash, "runtime.flash_attention_help"))
        form.addRow(self._t("runtime.jinja"), self._option_with_help(self.jinja, "runtime.jinja_help"))
        form.addRow(self._t("runtime.reasoning_format"), self.reasoning); form.addRow(self._t("runtime.parallel"), self.parallel); return group

    def _agent_group(self) -> QGroupBox:
        group = QGroupBox(self._t("agent.title")); form = QFormLayout(group)
        self.prompt_scheme_combo = QComboBox()
        self.delete_prompt_scheme_button = QPushButton(self._t("agent.delete_prompt_scheme"))
        self._refresh_prompt_scheme_combo("")
        self.new_prompt_scheme_button = QPushButton(self._t("agent.new_prompt_scheme"))
        self.save_prompt_scheme_button = QPushButton(self._t("agent.save_prompt_scheme"))
        scheme_buttons = QWidget(); buttons_layout = QHBoxLayout(scheme_buttons); buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.addWidget(self.new_prompt_scheme_button)
        buttons_layout.addWidget(self.save_prompt_scheme_button)
        buttons_layout.addWidget(self.delete_prompt_scheme_button)
        self.system_prompt = QPlainTextEdit(); self.system_prompt.setMinimumHeight(115)
        hint = QLabel(self._t("agent.prompt_hint")); hint.setWordWrap(True)
        form.addRow(self._t("agent.prompt_scheme"), self.prompt_scheme_combo)
        form.addRow("", scheme_buttons)
        form.addRow(self._t("agent.system_prompt"), self.system_prompt)
        form.addRow("", hint)
        return group

    def _command_group(self) -> QGroupBox:
        group = QGroupBox(self._t("command.title"))
        group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QVBoxLayout(group)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(110)
        layout.addWidget(self.preview)
        return group

    def _bind_events(self) -> None:
        self.preset_list.currentRowChanged.connect(self._select); self.preset_list.customContextMenuRequested.connect(self._preset_menu); self.new_button.clicked.connect(self._new); self.delete_button.clicked.connect(self._delete); self.save_button.clicked.connect(self._save)
        self.start_button.clicked.connect(lambda: self.server_manager.start(self._form_config())); self.stop_button.clicked.connect(self.server_manager.stop); self.restart_button.clicked.connect(lambda: self.server_manager.restart(self._form_config())); self.clear_button.clicked.connect(self.log_view.clear)
        self.browser_copy_button.clicked.connect(lambda: self._copy_address(self.browser_address))
        self.api_copy_button.clicked.connect(lambda: self._copy_address(self.api_address))
        self.port.valueChanged.connect(self._update_addresses)
        self.context_combo.currentIndexChanged.connect(self._context_mode_changed); self.context_custom.valueChanged.connect(self._context_changed); self.model_edit.textChanged.connect(self._model_changed); self.server_manager.state_changed.connect(self._update_state); self.server_manager.process_id_changed.connect(self._update_pid); self.server_manager.log_received.connect(self._log)
        self.prompt_scheme_combo.currentIndexChanged.connect(self._select_prompt_scheme)
        self.new_prompt_scheme_button.clicked.connect(self._new_prompt_scheme)
        self.save_prompt_scheme_button.clicked.connect(self._save_prompt_scheme)
        self.delete_prompt_scheme_button.clicked.connect(self._delete_prompt_scheme)
        self.server_manager.token_speed_changed.connect(self._update_token_speed)
        for control in (self.name_edit, self.server_edit, self.model_edit, self.mmproj_edit, self.port, self.gpu, self.parallel, self.flash, self.jinja, self.reasoning, self.mtp_edit):
            (getattr(control, "textChanged", None) or getattr(control, "valueChanged", None) or getattr(control, "toggled", None) or getattr(control, "currentTextChanged")).connect(self._preview)

    def _picker(self, target: QLineEdit, title: str, file_filter: str) -> QPushButton:
        button = QPushButton(self._t("common.browse"))
        def select() -> None:
            path, _ = QFileDialog.getOpenFileName(self, self._t(title), str(Path(target.text()).parent) if target.text() else "", self._t(file_filter))
            if path: target.setText(path)
        button.clicked.connect(select); return button

    @staticmethod
    def _with_button(edit: QLineEdit, button: QPushButton) -> QWidget:
        box = QWidget(); layout = QHBoxLayout(box); layout.setContentsMargins(0, 0, 0, 0); layout.addWidget(edit); layout.addWidget(button); return box

    def _option_with_help(self, checkbox: QCheckBox, help_key: str) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        description = QLabel(self._t(help_key))
        description.setWordWrap(True)
        description.setStyleSheet("color: #666;")
        checkbox.setToolTip(self._t(help_key))
        layout.addWidget(checkbox)
        layout.addWidget(description, 1)
        return box

    @staticmethod
    def _spin(low: int, high: int, value: int) -> QSpinBox:
        spin = QSpinBox(); spin.setRange(low, high); spin.setValue(value); return spin

    def _form_config(self) -> ServerConfig:
        scheme = str(self.prompt_scheme_combo.currentData() or "")
        prompt = self.system_prompt.toPlainText() if scheme else self.presets[self.selected_index].system_prompt
        return ServerConfig(id=self.presets[self.selected_index].id, name=self.name_edit.text().strip() or self._t("preset.untitled"), server_path=self.server_edit.text().strip(), model_path=self.model_edit.text().strip(), mmproj_path=self.mmproj_edit.text().strip(), mtp_path=self.mtp_edit.text().strip(), port=self.port.value(), context_length=self._context_value(), gpu_layers=self.gpu.value(), flash_attention=self.flash.isChecked(), jinja=self.jinja.isChecked(), reasoning_format=self.reasoning.currentText(), parallel=self.parallel.value(), agent_profile=self.presets[self.selected_index].agent_profile, system_prompt_scheme=scheme, system_prompt=prompt)
    def _load(self, config: ServerConfig) -> None:
        self._loading_preset = True
        self.name_edit.setText(config.name); self.server_edit.setText(config.server_path); self.model_edit.setText(config.model_path); self.mmproj_edit.setText(config.mmproj_path); self.port.setValue(config.port); self._set_context_value(config.context_length); self.gpu.setValue(config.gpu_layers); self.flash.setChecked(config.flash_attention); self.jinja.setChecked(config.jinja); self.reasoning.setCurrentText(config.reasoning_format); self.parallel.setValue(config.parallel)
        self.mtp_edit.setText(config.mtp_path)
        scheme_index = self.prompt_scheme_combo.findData(config.system_prompt_scheme)
        self.prompt_scheme_combo.setCurrentIndex(scheme_index if scheme_index >= 0 else 0)
        self.system_prompt.setPlainText(self.prompt_schemes.get(config.system_prompt_scheme, "")); self._loading_preset = False; self._model_changed(config.model_path); self._preview()
    def _preview(self, *_: object) -> None: self.preview.setPlainText(CommandBuilder.build_command_preview(self._form_config()))
    def _context_value(self) -> int: return int(self.context_combo.currentData()) if self.context_combo.currentData() is not None else self.context_custom.value()
    def _set_context_value(self, value: int) -> None:
        index = self.context_combo.findData(value)
        self.context_combo.setCurrentIndex(index if index >= 0 else self.context_combo.count() - 1)
        self.context_custom.setValue(value); self.context_custom.setVisible(index < 0); self._context_changed()
    def _context_mode_changed(self, _: int) -> None:
        self.context_custom.setVisible(self.context_combo.currentData() is None); self._context_changed()
    def _context_changed(self, *_: object) -> None:
        self._preview(); maximum = self.model_context_length; current = self._context_value()
        show_warning = bool(maximum and current > maximum)
        self.context_warning.setText(self._t("runtime.context_warning", maximum=self._format_context(maximum), current=self._format_context(current)) if show_warning else "")
        self.runtime_form.setRowVisible(self.context_warning, show_warning)
    def _model_changed(self, path: str) -> None:
        self.model_context_length = GGUFMetadataReader.read_context_length(path) if path.lower().endswith(".gguf") else None; self._context_changed()
    @staticmethod
    def _format_context(value: int) -> str: return f"{value // 1024}K" if value % 1024 == 0 else str(value)
    def _refresh_list(self) -> None:
        self.preset_list.blockSignals(True); self.preset_list.clear(); self.preset_list.addItems([item.name for item in self.presets]); self.preset_list.blockSignals(False)
    def _select(self, row: int) -> None:
        if not 0 <= row < len(self.presets): return
        if row != self.selected_index:
            self.presets[self.selected_index] = self._form_config()
        self.selected_index = row; self._load(self.presets[row])
    def _save(self) -> None:
        config = self._form_config(); self.presets[self.selected_index] = config; self._refresh_list(); self.preset_list.setCurrentRow(self.selected_index); self._persist(); self._log(f"{self._t('preset.saved', name=config.name)}\n")
    def _new(self) -> None:
        name, accepted = QInputDialog.getText(self, self._t("preset.new"), self._t("preset.name_prompt"), text=self._t("preset.new_name", number=len(self.presets) + 1))
        if not accepted or not name.strip(): return
        self.presets[self.selected_index] = self._form_config()
        config = self._form_config(); config.id = uuid.uuid4().hex; config.name = name.strip(); self.presets.append(config); self.selected_index = len(self.presets) - 1; self._refresh_list(); self.preset_list.setCurrentRow(self.selected_index); self._save()
    def _delete(self) -> None:
        if len(self.presets) == 1: QMessageBox.information(self, self._t("common.information"), self._t("preset.minimum_one")); return
        deleted = self.presets.pop(self.selected_index); self.selected_index = max(0, self.selected_index - 1)
        self._refresh_list(); self.preset_list.blockSignals(True); self.preset_list.setCurrentRow(self.selected_index); self.preset_list.blockSignals(False)
        self._load(self.presets[self.selected_index]); self._persist(); self._log(f"{self._t('preset.deleted', name=deleted.name)}\n")
    def _rename(self) -> None:
        current = self._form_config()
        name, accepted = QInputDialog.getText(self, self._t("preset.rename"), self._t("preset.name_prompt"), text=current.name)
        if accepted and name.strip(): current.name = name.strip(); self.presets[self.selected_index] = current; self._load(current); self._save()
    def _duplicate(self) -> None:
        original = self._form_config()
        name, accepted = QInputDialog.getText(self, self._t("preset.duplicate"), self._t("preset.name_prompt"), text=self._t("preset.copy_name", name=original.name))
        if not accepted or not name.strip(): return
        self.presets[self.selected_index] = original
        original = self._form_config(); original.id = uuid.uuid4().hex
        original.name = name.strip(); self.presets.append(original); self.selected_index = len(self.presets) - 1; self._refresh_list(); self.preset_list.setCurrentRow(self.selected_index); self._save()
    def _preset_menu(self, position) -> None:
        row = self.preset_list.indexAt(position).row()
        if row < 0: return
        self.preset_list.setCurrentRow(row); menu = QMenu(self)
        start = menu.addAction(self._t("server.start")); stop = menu.addAction(self._t("server.stop")); menu.addSeparator()
        duplicate = menu.addAction(self._t("preset.duplicate")); rename = menu.addAction(self._t("preset.rename")); delete = menu.addAction(self._t("preset.delete"))
        action = menu.exec(self.preset_list.mapToGlobal(position))
        if action == start: self.server_manager.start(self._form_config())
        elif action == stop: self.server_manager.stop()
        elif action == duplicate: self._duplicate()
        elif action == rename: self._rename()
        elif action == delete: self._delete()
    def _refresh_prompt_scheme_combo(self, selected: str) -> None:
        combo = self.prompt_scheme_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(self._t("agent.no_prompt_scheme"), "")
        for name in sorted(self.prompt_schemes, key=str.casefold):
            combo.addItem(name, name)
        index = combo.findData(selected)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)
        self.delete_prompt_scheme_button.setEnabled(bool(combo.currentData()))

    def _select_prompt_scheme(self, _: int) -> None:
        self.delete_prompt_scheme_button.setEnabled(bool(self.prompt_scheme_combo.currentData()))
        if self._loading_preset:
            return
        name = self.prompt_scheme_combo.currentData()
        if name in self.prompt_schemes:
            self.system_prompt.setPlainText(self.prompt_schemes[name])
        else:
            self.system_prompt.clear()

    def _new_prompt_scheme(self) -> None:
        name, accepted = QInputDialog.getText(
            self, self._t("agent.new_prompt_scheme"), self._t("agent.prompt_scheme_name")
        )
        if not accepted or not name.strip():
            return
        name = name.strip()
        if any(existing.casefold() == name.casefold() for existing in self.prompt_schemes):
            QMessageBox.warning(self, self._t("common.information"), self._t("agent.prompt_scheme_exists"))
            return
        self.prompt_schemes[name] = self.system_prompt.toPlainText()
        self._refresh_prompt_scheme_combo(name)
        self._persist_prompt_scheme()

    def _save_prompt_scheme(self) -> None:
        name = self.prompt_scheme_combo.currentData()
        if not name:
            self._new_prompt_scheme()
            return
        self.prompt_schemes[name] = self.system_prompt.toPlainText()
        self._persist_prompt_scheme()

    def _delete_prompt_scheme(self) -> None:
        name = self.prompt_scheme_combo.currentData()
        if not name or name not in self.prompt_schemes:
            return
        answer = QMessageBox.question(
            self,
            self._t("agent.delete_prompt_scheme"),
            self._t("agent.delete_prompt_scheme_confirm", name=name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.presets[self.selected_index] = self._form_config()
        del self.prompt_schemes[name]
        for preset in self.presets:
            if preset.system_prompt_scheme == name:
                preset.system_prompt_scheme = ""
        self._refresh_prompt_scheme_combo("")
        self.system_prompt.clear()
        self._persist()
        self._log(f"{self._t('agent.prompt_scheme_deleted', name=name)}\n")

    def _persist_prompt_scheme(self) -> None:
        self.presets[self.selected_index] = self._form_config()
        self._persist()
        self._log(f"{self._t('agent.prompt_scheme_saved', name=self.prompt_scheme_combo.currentData())}\n")
    def _update_state(self, state: ServerState) -> None:
        keys = {ServerState.STOPPED:"server.stopped",ServerState.STARTING:"server.starting",ServerState.RUNNING:"server.running",ServerState.FAILED:"server.failed"}; colors = {ServerState.STOPPED:"#777",ServerState.STARTING:"#d98c00",ServerState.RUNNING:"#198754",ServerState.FAILED:"#c62828"}
        self.status_label.setText(self._t(keys[state])); self.status_label.setStyleSheet(f"color: {colors[state]}; font-weight: 600;"); active = state in (ServerState.STARTING, ServerState.RUNNING); self.start_button.setEnabled(not active); self.stop_button.setEnabled(active); self.restart_button.setEnabled(active)
        self._update_addresses()

    def _update_addresses(self, *_: object) -> None:
        port = self.server_manager.active_port or self.port.value()
        base = f"http://127.0.0.1:{port}"
        self.browser_address.setText(f"{base}/")
        self.api_address.setText(f"{base}/v1")

    def _copy_address(self, field: QLineEdit) -> None:
        QApplication.clipboard().setText(field.text())
    def _update_pid(self, pid: int) -> None: self.pid_label.setText(str(pid) if pid else "-")
    def _update_token_speed(self, speed: float) -> None:
        self.token_speed_label.setText(f"{speed:.1f} token/s")
    def _log(self, text: str) -> None: self.log_view.moveCursor(QTextCursor.End); self.log_view.insertPlainText(text); self.log_view.ensureCursorVisible()
    def _set_language(self, language: str) -> None:
        if language == self.language:
            return
        self.presets[self.selected_index] = self._form_config()
        logs = self.log_view.toPlainText()
        self.server_manager.state_changed.disconnect(self._update_state)
        self.server_manager.process_id_changed.disconnect(self._update_pid)
        self.server_manager.log_received.disconnect(self._log)
        self.server_manager.token_speed_changed.disconnect(self._update_token_speed)
        self.language = language
        self.translator.load(language)
        self._persist()
        old = self.takeCentralWidget()
        if old:
            old.deleteLater()
        self._build_window(logs + f"{self._t('settings.language_changed')}\n")
    def _persist(self) -> None:
        self.config_service.save_presets(
            self.presets, self.selected_index, self.language, self.prompt_schemes
        )
    def needs_first_setup(self) -> bool:
        config = self.presets[self.selected_index]
        return not Path(config.server_path).is_file() or not Path(config.model_path).is_file()
    def run_first_setup(self) -> None:
        wizard = FirstSetupWizard(self.translator, self)
        if wizard.exec() == wizard.Accepted:
            self.server_edit.setText(wizard.server_path); self.model_edit.setText(wizard.model_path); self._save()
    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.presets[self.selected_index] = self._form_config(); self._persist()
        self.server_manager.shutdown()
        event.accept()
