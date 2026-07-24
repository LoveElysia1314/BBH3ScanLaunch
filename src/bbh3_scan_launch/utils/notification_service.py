# -*- coding: utf-8 -*-
"""
通知服务抽象
"""

from typing import Callable
import logging


class NotificationSink:
    """
    轻量消息通知适配器。
    在核心模块中注入，避免与 UI 库耦合。
    """

    def __init__(
        self,
        info_handler: Callable[[str, str], None] = None,
        warning_handler: Callable[[str, str], None] = None,
    ):
        self.info_handler = info_handler if info_handler else self._default_info_handler
        self.warning_handler = (
            warning_handler if warning_handler else self._default_warning_handler
        )

    @staticmethod
    def _default_info_handler(title: str, message: str) -> None:
        logging.info(f"{title}: {message}")

    @staticmethod
    def _default_warning_handler(title: str, message: str) -> None:
        logging.warning(f"{title}: {message}")

    def info(self, title: str, message: str) -> None:
        self.info_handler(title, message)

    def warning(self, title: str, message: str) -> None:
        self.warning_handler(title, message)


def create_noop_sink() -> NotificationSink:
    """静默Sink：完全不输出。用于后台流程/不展示UI的场景。"""

    def noop(_title: str, _message: str) -> None:
        return None

    return NotificationSink(noop, noop)


def create_qt_sink() -> NotificationSink:
    """返回基于 PySide6 的消息弹窗 Sink。"""

    def info(title: str, message: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(None, title, message)

    def warning(title: str, message: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(None, title, message)

    return NotificationSink(info_handler=info, warning_handler=warning)
