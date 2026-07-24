# -*- coding: utf-8 -*-
"""后台线程工作项。

将耗时操作放入 QThread 子类，避免主线程阻塞。
"""

import asyncio
import logging

from PySide6.QtCore import QThread, Signal

from ..utils.exception_utils import handle_exceptions


class UpdateDownloadThread(QThread):
    """后台线程：执行更新下载操作，避免阻塞主线程。"""

    update_status = Signal(str)

    def __init__(self, update_service):
        super().__init__()
        self._update_service = update_service

    def run(self):
        # 检查是否已被请求停止
        if self.isInterruptionRequested():
            return

        self.update_status.emit("正在准备下载...")

        # 尝试按优先级下载
        try:
            success = self._update_service.open_best_download()
        except Exception as exc:
            logging.exception("更新下载失败")
            self.update_status.emit(f"更新下载失败: {exc}")
            return

        # 再次检查是否已被请求停止
        if self.isInterruptionRequested():
            return

        if success:
            self.update_status.emit("已在浏览器中打开下载链接")
        else:
            self.update_status.emit("所有下载源均不可用")


class UpdateCheckThread(QThread):
    """后台线程：检查更新并发射结果信号。"""

    update_result = Signal(bool, str)
    update_status = Signal(str)
    update_failed = Signal(str)

    def __init__(self, update_service):
        super().__init__()
        self._update_service = update_service

    def run(self):
        # 发送状态：开始检查更新
        self.update_status.emit("正在获取远程版本信息...")

        # 使用注入的服务检查更新
        try:
            update_info = self._update_service.check_update()
        except Exception as exc:
            logging.exception("更新检查失败")
            self.update_failed.emit(str(exc))
            return

        if update_info.get("error"):
            self.update_failed.emit(update_info["error"])
            return

        if update_info.get("has_update"):
            self.update_status.emit("发现新版本")
            self.update_result.emit(True, update_info["remote_version"])
        else:
            self.update_status.emit("当前已是最新版本")
            self.update_result.emit(False, update_info.get("current_version", "未知"))


class LoginThread(QThread):
    """后台线程：处理账号登录。"""

    update_log = Signal(str)
    login_complete = Signal(bool)

    def __init__(self, auth_service):
        super().__init__()
        self._auth_service = auth_service

    @handle_exceptions("登陆过程中发生错误", None)
    def run(self):
        result = asyncio.run(self._auth_service.authenticate())
        self.login_complete.emit(bool(result))


class ParseThread(QThread):
    """后台线程：执行二维码解析与自动点击主循环。"""

    update_log = Signal(str)
    exit_app = Signal()

    def __init__(self, game_manager, config_manager, image_processor):
        super().__init__()
        self._game_manager = game_manager
        self._config_manager = config_manager
        self._image_processor = image_processor

    async def periodic_check(self):
        """定期执行检查任务"""
        await self._game_manager.auto_monitor(
            self._config_manager.get_effective_config(),
            self._image_processor,
            self.exit_app.emit if hasattr(self, "exit_app") else None,
        )

    def run(self):
        asyncio.run(self.periodic_check())
