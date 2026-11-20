"""Только один экземпляр приложения.

Первый экземпляр слушает локальный сокет (именованный канал на Windows).
Повторный запуск подключается к нему, разрешает первому процессу вывести
окно на передний план (``AllowSetForegroundWindow``) и сразу завершается.
"""

from __future__ import annotations

import getpass
import hashlib
import logging
import os
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

log = logging.getLogger(__name__)

_TIMEOUT_MS = 1500
_ACTIVATE = b"activate\n"


def _server_name(app_id: str) -> str:
    try:
        user = getpass.getuser()
    except Exception:  # pragma: no cover
        user = "user"
    digest = hashlib.sha1(f"{app_id}:{user}".encode()).hexdigest()[:12]
    return f"{app_id}-{digest}"


class SingleInstance(QObject):
    """``is_primary`` — True, если мы первый экземпляр.

    Сигнал :attr:`activation_requested` срабатывает, когда кто-то запустил
    приложение повторно.
    """

    activation_requested = Signal()

    def __init__(self, app_id: str = "Grasp", parent: QObject | None = None) -> None:
        # Родитель — приложение: объектом владеет Qt, и сборщик мусора Python
        # не удалит сервер с живыми сокетами (это приводило к падению).
        from PySide6.QtCore import QCoreApplication

        super().__init__(parent or QCoreApplication.instance())
        self.name = os.environ.get("GRASP_INSTANCE_NAME") or _server_name(app_id)
        self._server: QLocalServer | None = None
        self._sockets: list[QLocalSocket] = []  # явное владение: см. close()
        self._mutex = None
        self.is_primary = not self._notify_running_instance()
        if self.is_primary:
            self._listen()
            self._create_windows_mutex(app_id)

    # -- вторичный экземпляр -------------------------------------------------
    def _notify_running_instance(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(_TIMEOUT_MS):
            return False
        # Первый экземпляр присылает свой PID, чтобы мы разрешили ему
        # забрать фокус (иначе Windows лишь мигнёт кнопкой на панели задач).
        if socket.waitForReadyRead(_TIMEOUT_MS):
            try:
                pid = int(bytes(socket.readAll()).decode().strip() or 0)
            except ValueError:
                pid = 0
            if pid and sys.platform == "win32":
                try:
                    import ctypes

                    ctypes.windll.user32.AllowSetForegroundWindow(pid)
                except Exception:  # pragma: no cover
                    pass
        socket.write(_ACTIVATE)
        socket.flush()
        socket.waitForBytesWritten(_TIMEOUT_MS)
        socket.disconnectFromServer()
        log.info("Приложение уже запущено — передан сигнал активации")
        return True

    # -- первичный экземпляр -------------------------------------------------
    def _listen(self) -> None:
        server = QLocalServer(self)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(self.name):
            # Остался сокет от упавшего процесса — удаляем и пробуем снова.
            QLocalServer.removeServer(self.name)
            if not server.listen(self.name):
                log.warning("Не удалось открыть локальный сервер: %s", server.errorString())
                return
        server.newConnection.connect(self._on_connection)
        self._server = server

    def _on_connection(self) -> None:
        assert self._server is not None
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.write(f"{os.getpid()}\n".encode())
            socket.flush()

            buffer = bytearray()

            def on_ready(sock: QLocalSocket = socket, buf: bytearray = buffer) -> None:
                buf.extend(bytes(sock.readAll()))
                if _ACTIVATE.strip() in buf:
                    buf.clear()
                    self.activation_requested.emit()

            socket.readyRead.connect(on_ready)
            socket.disconnected.connect(lambda sock=socket: self._drop(sock))
            self._sockets.append(socket)
            # Данные могли прийти до подключения сигнала readyRead.
            if socket.bytesAvailable():
                on_ready()

    def _create_windows_mutex(self, app_id: str) -> None:
        """Именованный мьютекс — по нему установщик (AppMutex) видит, что
        программа запущена, и просит её закрыть перед обновлением."""
        if sys.platform != "win32":
            return
        try:
            import ctypes

            self._mutex = ctypes.windll.kernel32.CreateMutexW(None, False, f"{app_id}AppMutex")
        except Exception:  # pragma: no cover
            self._mutex = None

    def _drop(self, sock: QLocalSocket) -> None:
        if sock in self._sockets:
            self._sockets.remove(sock)
            sock.deleteLater()

    def close(self) -> None:
        """Перестать принимать подключения (объекты удалит Qt вместе с приложением)."""
        for sock in self._sockets:
            try:
                sock.readyRead.disconnect()
                sock.disconnected.disconnect()
            except (RuntimeError, TypeError):
                pass
            sock.abort()
        if self._server is not None:
            self._server.close()
