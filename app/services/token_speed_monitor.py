"""Read live generation throughput from llama-server's local /slots endpoint."""

from __future__ import annotations

import json
import time

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkProxy, QNetworkReply, QNetworkRequest


def slot_token_counts(payload: object) -> dict[tuple[int, int], int]:
    """Return decoded-token counters for slots currently processing requests."""
    if not isinstance(payload, list):
        return {}
    counts: dict[tuple[int, int], int] = {}
    for slot in payload:
        if not isinstance(slot, dict) or slot.get("is_processing") is not True:
            continue
        next_token = slot.get("next_token")
        if isinstance(next_token, dict):
            token_entries = [next_token]
        elif isinstance(next_token, list):
            token_entries = next_token
        else:
            continue
        slot_id, task_id = slot.get("id"), slot.get("id_task")
        decoded_values = [entry.get("n_decoded") for entry in token_entries if isinstance(entry, dict)]
        if not decoded_values or any(type(value) is not int or value < 0 for value in decoded_values):
            continue
        decoded = sum(decoded_values)
        if (type(slot_id) is int and type(task_id) is int
                and type(decoded) is int and decoded >= 0):
            counts[(slot_id, task_id)] = decoded
    return counts


class TokenSpeedMonitor(QObject):
    """Poll only the server started by this application; never intercept API calls."""

    speed_changed = Signal(float)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._network = QNetworkAccessManager(self)
        self._network.setProxy(QNetworkProxy(QNetworkProxy.NoProxy))
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll)
        self._url: QUrl | None = None
        self._reply: QNetworkReply | None = None
        self._generation = 0
        self._previous: dict[tuple[int, int], tuple[int, float]] = {}
        self.speed = 0.0

    def start(self, port: int) -> None:
        self.stop()
        self._url = QUrl(f"http://127.0.0.1:{port}/slots")
        self._timer.start()
        self._poll()

    def stop(self) -> None:
        self._timer.stop()
        self._url = None
        self._generation += 1
        self._previous.clear()
        if self._reply is not None:
            reply, self._reply = self._reply, None
            reply.abort()
        self._set_speed(0.0)

    def _poll(self) -> None:
        if self._url is None or self._reply is not None:
            return
        request = QNetworkRequest(self._url)
        request.setTransferTimeout(1500)
        reply = self._network.get(request)
        self._reply = reply
        generation = self._generation
        reply.finished.connect(lambda: self._handle_reply(reply, generation))

    def _handle_reply(self, reply: QNetworkReply, generation: int) -> None:
        if self._reply is reply:
            self._reply = None
        body = bytes(reply.readAll())
        error = reply.error()
        reply.deleteLater()
        if generation != self._generation:
            return
        if error != QNetworkReply.NoError:
            self._previous.clear()
            self._set_speed(0.0)
            return
        try:
            counts = slot_token_counts(json.loads(body))
        except (UnicodeDecodeError, json.JSONDecodeError):
            counts = {}
        now = time.monotonic()
        speeds = []
        for key, count in counts.items():
            previous = self._previous.get(key)
            if previous and count >= previous[0] and now > previous[1]:
                speeds.append((count - previous[0]) / (now - previous[1]))
        self._previous = {key: (count, now) for key, count in counts.items()}
        self._set_speed(sum(speeds))

    def _set_speed(self, value: float) -> None:
        self.speed = value
        self.speed_changed.emit(value)
