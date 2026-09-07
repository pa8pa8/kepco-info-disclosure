from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import threading
import time

import uvicorn

from ..config import AI_BUNDLE_DIR, AI_SERVER_HOST, AI_SERVER_PORT, INTERNAL_AI_API_URL

logger = logging.getLogger(__name__)


class LocalAIServer:
    """Runs the bundled identify API on localhost for the dashboard."""

    def __init__(self, host: str = AI_SERVER_HOST, port: int = AI_SERVER_PORT):
        self.host = host
        self.port = port
        self.url = INTERNAL_AI_API_URL
        self._thread: threading.Thread | None = None
        self._server: uvicorn.Server | None = None
        self._process: subprocess.Popen | None = None

    def is_port_open(self) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=0.3):
                return True
        except OSError:
            return False

    def start(self) -> None:
        if self.is_port_open():
            logger.info('[local-ai] already listening on %s', self.url)
            return
        if self._thread and self._thread.is_alive():
            return
        if self._process and self._process.poll() is None:
            return

        exe_path = AI_BUNDLE_DIR / 'api_server.exe'
        use_internal_api = os.getenv('FOIA_AI_USE_INTERNAL', '').lower() in ('1', 'true', 'yes')
        if exe_path.exists() and not use_internal_api:
            self._start_sidecar_exe(exe_path)
            return

        config = uvicorn.Config(
            'app.ai_runtime.api:app',
            host=self.host,
            port=self.port,
            log_level='warning',
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name='local-ai-server', daemon=True)
        self._thread.start()

        for _ in range(30):
            if self.is_port_open():
                logger.info('[local-ai] started on %s', self.url)
                return
            time.sleep(0.1)
        logger.warning('[local-ai] start requested but port did not open within timeout')

    def _start_sidecar_exe(self, exe_path):
        logger.info('[local-ai] starting sidecar exe: %s', exe_path)
        creationflags = 0
        startupinfo = None
        if sys.platform.startswith('win'):
            creationflags = (
                getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
            )
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self._process = subprocess.Popen(
            [str(exe_path)],
            cwd=str(AI_BUNDLE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
        for _ in range(120):
            if self.is_port_open():
                logger.info('[local-ai] sidecar started on %s', self.url)
                return
            if self._process.poll() is not None:
                logger.warning('[local-ai] sidecar exited early with code %s', self._process.returncode)
                return
            time.sleep(0.25)
        logger.warning('[local-ai] sidecar did not open port within timeout')

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
