# -*- coding: utf-8 -*-
# 标准库 imports
import os
import sys
import inspect
# 第三方库 imports
from PySide6.QtCore import Signal, QObject

def set_qt_env():
    """设置 Qt 环境变量，解决打包后插件加载问题"""
    if getattr(sys, 'frozen', False):
        # 打包后模式：使用临时目录
        base_dir = sys._MEIPASS
    else:
        # 开发模式：使用当前目录
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 设置 Qt 插件路径
    os.environ['QT_PLUGIN_PATH'] = os.path.join(base_dir, 'plugins')
    os.environ['QML2_IMPORT_PATH'] = os.path.join(base_dir, 'qml')


# ========== DummyWriter 和 EmittingStream 类：用于拦截 stdout 输出 ==========

class DummyWriter:
    def write(self, text):
        pass

    def flush(self):
        pass

class EmittingStream(QObject):
    textWritten = Signal(str)

    def __init__(self):
        super().__init__()

        # 确保 original_stdout 不为 None
        self.original_stdout = sys.stdout if sys.stdout is not None else DummyWriter()
        self._buffer = ""

        # 控制选项
        self.show_debug_gui = False     # 是否在 GUI 中显示 DEBUG
        self.show_debug_terminal = False  # 是否在终端中显示 DEBUG

        # 自动判断是否运行在无控制台模式下
        if sys.stdout is None or isinstance(sys.stdout, DummyWriter):
            self.show_debug_terminal = False
        else:
            self.show_debug_terminal = True

    def write(self, text):
        # 先缓存文本
        self._buffer += text

        # 如果有换行符，则处理每一行
        if '\n' in self._buffer:
            lines = self._buffer.split('\n')
            self._buffer = lines[-1]  # 最后一行可能是未完成的

            for line in lines[:-1]:
                full_line = line

                # 判断是否是 DEBUG 行
                is_debug = full_line.startswith("[DEBUG]")

                # 决定是否发送到 GUI
                if self.show_debug_gui or not is_debug:
                    self.textWritten.emit(full_line)

                # 决定是否输出到终端
                if self.show_debug_terminal or not is_debug:
                    self.original_stdout.write(full_line + '\n')  # 添加换行
                    self.original_stdout.flush()

    def flush(self):
        # 处理缓冲区最后的内容（可能没有换行）
        if self._buffer:
            full_line = self._buffer
            self._buffer = ""
            is_debug = full_line.startswith("[DEBUG]")

            # 发送到 GUI
            if self.show_debug_gui or not is_debug:
                self.textWritten.emit(full_line)

            # 输出到终端
            if self.show_debug_terminal or not is_debug:
                self.original_stdout.write(full_line)
                self.original_stdout.flush()

    def get_caller_info(self):
        import inspect
        frame = inspect.currentframe()
        try:
            outer_frame = frame.f_back.f_back
            filename = outer_frame.f_code.co_filename
            lineno = outer_frame.f_lineno
            modname = inspect.getmodule(outer_frame).__name__
            return f"[{modname} {filename}:{lineno}]"
        finally:
            del frame
