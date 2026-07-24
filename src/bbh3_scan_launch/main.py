# main.py
import sys
from .core.runtime_context import RuntimeContext
from .core.app_bootstrap import AppBootstrap
from .core.game_window import enable_per_monitor_dpi_awareness
from .utils.notification_service import create_qt_sink


# ========== 应用启动函数 ==========
def main():
    """运行应用程序的核心逻辑"""
    enable_per_monitor_dpi_awareness()
    runtime_context = RuntimeContext.build(create_qt_sink())
    exit_code = AppBootstrap(runtime_context).run(sys.argv)
    raise SystemExit(exit_code)


# ========== Flask 启动 ==========
if __name__ == "__main__":
    main()
