import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.models.server_config import ServerConfig
from app.services.command_builder import CommandBuilder
from app.services.localization import Translator
from app.services.server_manager import ServerManager, ServerState, health_response_ready


def test_health_response_requires_ready_status() -> None:
    assert not health_response_ready(503, b'{"status":"loading model"}')
    assert not health_response_ready(200, b'{"status":"loading model"}')
    assert not health_response_ready(200, b'not-json')
    assert health_response_ready(200, b'{"status":"ok"}')


def test_process_stays_preparing_until_health_is_ready(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])

    class HealthHandler(BaseHTTPRequestHandler):
        ready = False
        requests = 0

        def do_GET(self) -> None:
            type(self).requests += 1
            status = 200 if type(self).ready else 503
            body = b'{"status":"ok"}' if type(self).ready else b'{"status":"loading model"}'
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass  # Stopping the manager can abort an in-flight health request.

        def log_message(self, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    model = tmp_path / "model.gguf"
    model.write_bytes(b"test")
    monkeypatch.setattr(CommandBuilder, "build_arguments", staticmethod(
        lambda _config: ["-c", "import time; time.sleep(10)"]
    ))
    manager = ServerManager(Translator())
    logs: list[str] = []
    manager.log_received.connect(logs.append)
    try:
        config = ServerConfig(
            server_path=sys.executable,
            model_path=str(model),
            port=server.server_address[1],
        )
        assert manager.start(config)
        deadline = time.monotonic() + 4
        while HealthHandler.requests < 1 and time.monotonic() < deadline:
            QTest.qWait(25)
        assert HealthHandler.requests >= 1
        assert manager.state == ServerState.STARTING
        assert manager.token_speed == 0.0

        manager.stop()
        deadline = time.monotonic() + 4
        while manager.state != ServerState.STOPPED and time.monotonic() < deadline:
            QTest.qWait(25)
        assert manager.state == ServerState.STOPPED
        assert not manager._health_timer.isActive()

        HealthHandler.ready = True
        QTest.qWait(1_100)
        assert manager.state == ServerState.STOPPED
        assert manager.start(config)
        deadline = time.monotonic() + 4
        while manager.state != ServerState.RUNNING and time.monotonic() < deadline:
            QTest.qWait(25)
        assert manager.state == ServerState.RUNNING
        assert "模型加载完成" in "".join(logs)
        manager.stop()
        deadline = time.monotonic() + 4
        while manager.state != ServerState.STOPPED and time.monotonic() < deadline:
            QTest.qWait(25)
        assert manager.state == ServerState.STOPPED
    finally:
        manager.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
