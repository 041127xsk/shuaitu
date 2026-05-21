"""
战报助手 - 自动翻页模块
"""
import threading
import time
from typing import Callable, Optional

from .adb_helper import ADBHelper


class AutoScroller:
    def __init__(self, adb: ADBHelper):
        self.adb = adb
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_progress: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

    def set_callbacks(self, on_progress=None, on_complete=None, on_error=None):
        """设置回调函数"""
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._on_error = on_error

    def start(self, count: int = 5000, delay: float = 0.1, duration: int = 100):
        """开始翻页"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._scroll_worker,
            args=(count, delay, duration),
            daemon=True
        )
        self._thread.start()

    def stop(self):
        """停止翻页"""
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def _scroll_worker(self, count: int, delay: float, duration: int):
        """翻页工作线程"""
        try:
            w, h = self.adb.get_screen_size()
            cx = w // 2
            y_start = int(h * 0.4)
            y_end = int(h * 0.15)

            for i in range(count):
                if not self._running:
                    break

                self.adb.swipe(cx, y_start, cx, y_end, duration)

                if self._on_progress:
                    self._on_progress(i + 1, count)

                if i < count - 1:
                    time.sleep(delay)

            if self._on_complete:
                self._on_complete()

        except Exception as e:
            if self._on_error:
                self._on_error(str(e))
        finally:
            self._running = False
