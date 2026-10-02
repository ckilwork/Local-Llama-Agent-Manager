"""Single-process llama-server lifecycle management for the MVP."""

from __future__ import annotations

import os
import json
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkProxy, QNetworkReply, QNetworkRequest
from PySide6.QtCore import QUrl

from app.models.server_config import ServerConfig
from app.services.command_builder import CommandBuilder
from app.services.localization import Translator
from app.services.token_speed_monitor import TokenSpeedMonitor


class ServerState(str, Enum):
    STOPPED = "Stopped"
    STARTING = "Starting"
    RUNNING = "Running"
    FAILED = "Failed"


def health_response_ready(status_code: object, body: bytes) -> bool:
    """llama-server reports readiness only after its model has loaded."""
    if status_code != 200:
        return False
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("status") == "ok"


class ServerManager(QObject):
    """Starts one external llama-server.exe and streams its output to the UI."""

    state_changed = Signal(ServerState)
    log_received = Signal(str)
    process_id_changed = Signal(int)
    token_speed_changed = Signal(float)

    def __init__(self, translator: Translator, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._process = QProcess(self)
        self._state = ServerState.STOPPED
        self._restart_config: ServerConfig | None = None
        self._active_config: ServerConfig | None = None
        self._stop_requested = False
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._kill_if_still_running)
        self._speed_monitor = TokenSpeedMonitor(self)
        self._speed_monitor.speed_changed.connect(self.token_speed_changed)
        self._health_network = QNetworkAccessManager(self)
        self._health_network.setProxy(QNetworkProxy(QNetworkProxy.NoProxy))
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(1_000)
        self._health_timer.timeout.connect(self._poll_health)
        self._health_url: QUrl | None = None
        self._health_reply: QNetworkReply | None = None
        self._health_generation = 0

        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.started.connect(self._on_started)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    @property
    def state(self) -> ServerState:
        return self._state

    @property
    def process_id(self) -> int:
        return int(self._process.processId()) if self._process.state() != QProcess.NotRunning else 0

    @property
    def token_speed(self) -> float:
        return self._speed_monitor.speed

    @property
    def active_port(self) -> int | None:
        if self._active_config is not None and self._state in (ServerState.STARTING, ServerState.RUNNING):
            return self._active_config.port
        return None

    def start(self, config: ServerConfig) -> bool:
        """Start the configured executable. Returns False if launch is invalid."""
        if self._process.state() != QProcess.NotRunning:
            self.log_received.emit(f"{self._translator.text('server.already_active')}\n")
            return False

        error = self._validate(config)
        if error:
            self.log_received.emit(f"{error}\n")
            self._set_state(ServerState.FAILED)
            return False

        self._stop_requested = False
        self._active_config = config
        self._stop_health_check()
        self._speed_monitor.stop()
        self._process.setWorkingDirectory(str(Path(config.server_path).parent))
        self._process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
        self._set_state(ServerState.STARTING)
        self.log_received.emit(
            f"{self._translator.text('server.launch_command', command=CommandBuilder.build_command_preview(config))}\n\n"
        )
        self._process.start(config.server_path, CommandBuilder.build_arguments(config))
        return True

    def stop(self) -> None:
        """Request a graceful stop, then kill only if the process does not exit."""
        if self._process.state() == QProcess.NotRunning:
            return
        self._restart_config = None
        self._stop_requested = True
        self._stop_health_check()
        self._speed_monitor.stop()
        self.log_received.emit(f"{self._translator.text('server.stopping')}\n")
        self._request_process_stop()

    def restart(self, config: ServerConfig) -> None:
        """Restart with the supplied settings after the active process exits."""
        if self._process.state() == QProcess.NotRunning:
            self.start(config)
            return
        self._restart_config = config
        self._stop_requested = True
        self._stop_health_check()
        self._speed_monitor.stop()
        self.log_received.emit(f"{self._translator.text('server.restarting')}\n")
        self._request_process_stop()

    def shutdown(self) -> None:
        """Synchronously clean up the child process before the Qt app exits."""
        if self._process.state() == QProcess.NotRunning:
            return
        self._restart_config = None
        self._stop_requested = True
        self._stop_health_check()
        self._speed_monitor.stop()
        self._kill_timer.stop()
        if os.name == "nt":
            self._process.kill()
            self._process.waitForFinished(1_000)
        else:
            self._process.terminate()
            if not self._process.waitForFinished(3_000):
                self._process.kill()
                self._process.waitForFinished(1_000)

    def _request_process_stop(self) -> None:
        if os.name == "nt":
            # QProcess.terminate() sends WM_CLOSE on Windows. Console servers
            # without a Windows message loop cannot handle that message.
            self._process.kill()
        else:
            self._process.terminate()
            self._kill_timer.start(3_000)

    def _validate(self, config: ServerConfig) -> str | None:
        server_path = Path(config.server_path)
        if not config.server_path or not server_path.is_file():
            return self._translator.text("errors.server_missing")
        if not config.model_path or not Path(config.model_path).is_file():
            return self._translator.text("errors.model_missing")
        if not config.model_path.lower().endswith(".gguf"):
            return self._translator.text("errors.model_not_gguf")
        for optional_path in (config.mmproj_path, config.mtp_path):
            if optional_path and (not optional_path.lower().endswith(".gguf") or not Path(optional_path).is_file()):
                return self._translator.text("errors.optional_gguf_missing", path=optional_path)
        if not 1 <= config.port <= 65535:
            return self._translator.text("errors.port_invalid")
        if config.context_length < 1 or config.parallel < 1:
            return self._translator.text("errors.values_invalid")
        return None

    def _on_started(self) -> None:
        if self._active_config is not None:
            self._start_health_check(self._active_config.port)
        self.process_id_changed.emit(self.process_id)
        self.log_received.emit(f"{self._translator.text('server.started', pid=self.process_id)}\n")

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._kill_timer.stop()
        self._stop_health_check()
        self._speed_monitor.stop()
        self._active_config = None
        self._read_stdout()
        self._read_stderr()
        self.process_id_changed.emit(0)
        restart_config, self._restart_config = self._restart_config, None
        stopped_by_user = self._stop_requested
        self._stop_requested = False

        if restart_config:
            self.log_received.emit(f"{self._translator.text('server.restart_starting')}\n")
            self._set_state(ServerState.STOPPED)
            self.start(restart_config)
        elif stopped_by_user:
            self.log_received.emit(f"{self._translator.text('server.stopped_log')}\n")
            self._set_state(ServerState.STOPPED)
        else:
            self.log_received.emit(f"{self._translator.text('server.unexpected_exit', code=exit_code)}\n")
            self._set_state(ServerState.FAILED)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.Crashed and self._stop_requested:
            return
        self.log_received.emit(
            f"{self._translator.text('server.process_error', error=self._process.errorString(), kind=error.name)}\n"
        )
        if error == QProcess.FailedToStart:
            self._stop_health_check()
            self._speed_monitor.stop()
            self._active_config = None
            self._set_state(ServerState.FAILED)

    def _start_health_check(self, port: int) -> None:
        self._stop_health_check()
        self._health_url = QUrl(f"http://127.0.0.1:{port}/health")
        self._health_timer.start()
        self._poll_health()

    def _stop_health_check(self) -> None:
        self._health_timer.stop()
        self._health_url = None
        self._health_generation += 1
        if self._health_reply is not None:
            reply, self._health_reply = self._health_reply, None
            reply.abort()

    def _poll_health(self) -> None:
        if (self._health_url is None or self._health_reply is not None
                or self._process.state() != QProcess.Running
                or self._state != ServerState.STARTING or self._stop_requested):
            return
        request = QNetworkRequest(self._health_url)
        request.setTransferTimeout(1_500)
        reply = self._health_network.get(request)
        self._health_reply = reply
        generation = self._health_generation
        reply.finished.connect(lambda: self._handle_health_reply(reply, generation))

    def _handle_health_reply(self, reply: QNetworkReply, generation: int) -> None:
        if self._health_reply is reply:
            self._health_reply = None
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        body = bytes(reply.readAll())
        error = reply.error()
        reply.deleteLater()
        if (generation != self._health_generation or error != QNetworkReply.NoError
                or not health_response_ready(status, body)
                or self._state != ServerState.STARTING or self._stop_requested
                or self._process.state() != QProcess.Running):
            return
        self._stop_health_check()
        self._set_state(ServerState.RUNNING)
        if self._active_config is not None:
            self._speed_monitor.start(self._active_config.port)
        self.log_received.emit(f"{self._translator.text('server.ready')}\n")

    def _read_stdout(self) -> None:
        text = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if text:
            self.log_received.emit(text)

    def _read_stderr(self) -> None:
        text = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        if text:
            self.log_received.emit(text)

    def _kill_if_still_running(self) -> None:
        if self._process.state() != QProcess.NotRunning:
            self.log_received.emit(f"{self._translator.text('server.force_stop')}\n")
            self._process.kill()

    def _set_state(self, state: ServerState) -> None:
        if self._state != state:
            self._state = state
            self.state_changed.emit(state)
