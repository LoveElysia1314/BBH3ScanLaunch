# -*- coding: utf-8 -*-
"""将标准日志安全桥接到 Qt 文本控件。"""

import logging
from collections import deque

from PySide6.QtCore import QObject, Signal

from ..utils.exception_utils import handle_exceptions


class _LogEmitter(QObject):
    sig = Signal(str)


class GuiHandler(logging.Handler):
    """将日志安全追加到 QTextBrowser。"""

    def __init__(self, text_widget):
        super().__init__()
        self._emitter = _LogEmitter()
        self._emitter.sig.connect(text_widget.append)
        self.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        self._log_buffer = deque(maxlen=3)
        self.filter_enabled = True

    @handle_exceptions("日志输出失败", None)
    def emit(self, record):
        msg = self.format(record)
        if not msg.strip():
            return
        if self.filter_enabled and record.levelno in (logging.INFO, logging.DEBUG):
            if msg in self._log_buffer:
                return
            self._log_buffer.append(msg)
        self._emitter.sig.emit(msg)
