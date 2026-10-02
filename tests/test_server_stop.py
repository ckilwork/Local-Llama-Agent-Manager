import os
import sys
from time import monotonic

import pytest
from PySide6.QtCore import QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.services.localization import Translator
from app.services.server_manager import ServerManager, ServerState


@pytest.mark.skipif(os.name != "nt", reason="Windows QProcess stop behavior")
def test_user_stop_does_not_wait_for_timeout_or_report_crash() -> None:
    app = QApplication.instance() or QApplication([])
    manager = ServerManager(Translator())
    logs: list[str] = []
    manager.log_received.connect(logs.append)
    try:
        manager._process.start(sys.executable, ["-c", "import time; time.sleep(20)"])
        assert manager._process.waitForStarted(3000)
        started = monotonic()
        manager.stop()
        deadline = monotonic() + 2
        while manager._process.state() != QProcess.NotRunning and monotonic() < deadline:
            QTest.qWait(20)
        assert manager._process.state() == QProcess.NotRunning
        assert monotonic() - started < 2
        assert manager.state == ServerState.STOPPED
        assert not manager._kill_timer.isActive()
        assert "正在强制结束进程" not in "".join(logs)
        assert "Crashed" not in "".join(logs)
    finally:
        manager.shutdown()
