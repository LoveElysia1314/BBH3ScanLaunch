# -*- coding: utf-8 -*-
# 标准库 imports
import os
import sys

# 第三方库 imports
from PySide6.QtCore import Signal, QObject, Qt
from PySide6.QtWidgets import QApplication

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
    
    # 设置环境变量（解决 Windows 高 DPI 缩放问题）
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "1"
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

# ========== EmittingStream 类：用于拦截 stdout 输出 ==========
import sys
import inspect

class EmittingStream(QObject):
    textWritten = Signal(str)

    def __init__(self):
        super().__init__()
        self.original_stdout = sys.stdout
        self._buffer = ""  # 用于缓存未完成的一行

    def write(self, text):
        self.original_stdout.write(text)
        # 将新文本追加到缓冲区
        self._buffer += text
        # 检查是否有完整行（以换行符结尾）
        if '\n' in self._buffer:
            lines = self._buffer.split('\n')
            self._buffer = lines[-1]  # 最后一个是不完整的部分（或空字符串）
            for line in lines[:-1]:
                full_line = line
                # 过滤 [DEBUG] 开头的行
                if full_line.startswith("[DEBUG]"):
                    continue
                # 添加来源信息
#                source_info = self.get_caller_info()
#                formatted_line = f"{source_info} {full_line}"
                formatted_line = full_line
                # 发送信号
                self.textWritten.emit(formatted_line)

    def get_caller_info(self):
        """获取调用 print 的位置信息"""
        frame = inspect.currentframe()
        try:
            # 跳过前两层：write -> print -> 用户代码
            outer_frame = frame.f_back.f_back
            filename = outer_frame.f_code.co_filename
            lineno = outer_frame.f_lineno
            modname = inspect.getmodule(outer_frame).__name__
            return f"[{modname} {filename}:{lineno}]"
        finally:
            del frame

    def flush(self):
        if self._buffer:
            # 处理最后的残余内容（没有换行的情况）
            full_line = self._buffer
            self._buffer = ""

            if full_line.startswith("[DEBUG]"):
                return

            source_info = self.get_caller_info()
            formatted_line = f"{source_info} {full_line}"
            self.textWritten.emit(formatted_line)

        self.original_stdout.flush()