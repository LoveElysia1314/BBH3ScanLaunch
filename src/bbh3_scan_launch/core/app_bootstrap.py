# -*- coding: utf-8 -*-
"""应用启动与生命周期编排。"""

import logging
import atexit

from dataclasses import dataclass
from threading import Thread

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ..constants import TEMPLATE_WEB_DIR
from ..gui.application_window import ApplicationWindow
from ..gui import main_window as main_window_ui
from ..gui.logging_handler import GuiHandler
from .coordinator import AppCoordinator
from .services.captcha_server import create_captcha_server


@dataclass(frozen=True)
class WindowBundle:
    app: QApplication
    coordinator: AppCoordinator
    window: ApplicationWindow


@dataclass(frozen=True)
class AppBootstrap:
    """应用启动器：将 main.py 中的组织逻辑集中管理。"""

    runtime_context: object

    def _configure_logging(self, debug_enabled: bool) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if debug_enabled else logging.INFO)

    def _build_window_and_coordinator(
        self, args: list[str] | tuple[str, ...]
    ) -> WindowBundle:
        app = QApplication(args)
        coordinator = AppCoordinator(self.runtime_context)
        window = ApplicationWindow(
            context=self.runtime_context,
            ui=main_window_ui.create_main_window(
                version_manager=self.runtime_context.version_manager
            ),
            on_login_submit=coordinator.start_login,
        )
        window.ui.setupUi(window)
        window.bind_download_priority_widget()
        coordinator.attach(window, app)
        return WindowBundle(app=app, coordinator=coordinator, window=window)

    def _start_captcha_server(self, coordinator: object):
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        flask_app = create_captcha_server(
            TEMPLATE_WEB_DIR,
            on_captcha=coordinator.apply_captcha,
            on_complete=coordinator.captcha_completed.emit,
        )
        flask_thread = Thread(
            target=flask_app.run,
            daemon=True,
            kwargs={
                "host": "0.0.0.0",
                "port": 12983,
                "threaded": True,
                "use_reloader": False,
                "debug": False,
            },
        )
        flask_thread.start()
        return flask_thread

    @staticmethod
    def _attach_gui_log_handler(log_text_widget) -> None:
        root_logger = logging.getLogger()
        if any(
            isinstance(existing_handler, GuiHandler)
            for existing_handler in root_logger.handlers
        ):
            return
        root_logger.addHandler(GuiHandler(log_text_widget))

    def run(self, args: list[str] | tuple[str, ...]) -> int:
        config = self.runtime_context.config_manager.config
        self._configure_logging(config.get("debug_print", False))

        bundle = self._build_window_and_coordinator(args)
        app = bundle.app
        coordinator = bundle.coordinator
        window = bundle.window

        # 挂载 GUI 文本日志接收器
        self._attach_gui_log_handler(window.ui.logText)

        self._start_captcha_server(coordinator)

        # 应用初始配置并展示主窗口
        window.apply_initial_state(config)
        window.show()

        # 如果配置中有账号，启动登录流程
        if config.get("account"):
            logging.info("配置文件已有账号，尝试登陆中...")
            coordinator.start_login()

        # 启动后自动检查更新
        window.check_and_display_updates()

        # 处理命令行参数
        if "--auto-login" in args:
            QTimer.singleShot(100, window.one_click_login)
            logging.info("检测到自动登陆参数，将启动一键登陆模式")

        atexit.register(window.restore_original_settings)
        return app.exec()
