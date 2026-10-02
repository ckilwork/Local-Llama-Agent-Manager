import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import monotonic

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.services.token_speed_monitor import TokenSpeedMonitor, slot_token_counts


def test_slot_token_counts_ignores_idle_and_invalid_slots() -> None:
    assert slot_token_counts([
        {"id": 0, "id_task": 3, "is_processing": True, "next_token": {"n_decoded": 12}},
        {"id": 1, "id_task": 4, "is_processing": False, "next_token": {"n_decoded": 99}},
        {"id": 2, "id_task": 5, "is_processing": True, "next_token": {}},
        {"id": 3, "id_task": 6, "is_processing": True,
         "next_token": [{"n_decoded": 158}]},
    ]) == {(0, 3): 12, (3, 6): 158}


def test_live_token_speed_and_stop_reset() -> None:
    app = QApplication.instance() or QApplication([])
    slots = [{"id": 0, "id_task": 3, "is_processing": True,
              "next_token": [{"n_decoded": 10}]}]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/slots"
            body = json.dumps(slots).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monitor = TokenSpeedMonitor()
    try:
        monitor.start(server.server_port)
        deadline = monotonic() + 2
        while not monitor._previous and monotonic() < deadline:
            QTest.qWait(20)
        assert monitor.speed == 0

        slots[0]["next_token"][0]["n_decoded"] = 30
        QTest.qWait(100)
        monitor._poll()
        deadline = monotonic() + 2
        while monitor.speed == 0 and monotonic() < deadline:
            QTest.qWait(20)
        assert monitor.speed > 0

        slots[0]["is_processing"] = False
        monitor._poll()
        deadline = monotonic() + 2
        while monitor.speed > 0 and monotonic() < deadline:
            QTest.qWait(20)
        assert monitor.speed == 0

        monitor.stop()
        assert monitor.speed == 0
    finally:
        monitor.stop()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
