# -*- coding: utf-8 -*-
# 标准库 imports
import sys
from collections import deque
# 第三方库 imports
from PySide6.QtCore import Signal, QObject


class DummyWriter:
    """
    虚拟输出写入器
    在无控制台模式下替代标准输出，防止输出到终端
    """
    def write(self, text):
        pass

    def flush(self):
        pass

class EmittingStream(QObject):
    textWritten = Signal(str)

    def __init__(self):
        super().__init__()
        self.original_stdout = sys.stdout if sys.stdout is not None else DummyWriter()
        self._buffer = ""
        self.show_debug_gui = False
        self.show_debug_terminal = False if sys.stdout is None or isinstance(sys.stdout, DummyWriter) else True
        
        # 简单的重复检测
        self._recent_lines = deque(maxlen=3)  # 只保留最近3行
        self._repeat_counts = {}  # 重复计数

    def write(self, text):
        self._buffer += text

        if '\n' in self._buffer:
            lines = self._buffer.split('\n')
            self._buffer = lines[-1]

            for line in lines[:-1]:
                self._process_line(line.strip())

    def _process_line(self, line):
        if not line:
            return

        # 检查是否在最近3行中出现过
        if line in self._recent_lines:
            # 增加重复计数
            if line not in self._repeat_counts:
                self._repeat_counts[line] = 0
            self._repeat_counts[line] += 1
            
            # 如果重复超过2次，就过滤掉
            if self._repeat_counts[line] >= 2:
                return
        else:
            # 新行，重置计数
            if line in self._repeat_counts:
                del self._repeat_counts[line]

        # 添加到最近行
        self._recent_lines.append(line)

        # 正常输出
        self._emit_line(line)

    def _emit_line(self, line):
        is_debug = line.startswith("[DEBUG]")
        
        if self.show_debug_gui or not is_debug:
            self.textWritten.emit(line)
            
        if self.show_debug_terminal or not is_debug:
            try:
                self.original_stdout.write(line + '\n')
                self.original_stdout.flush()
            except:
                pass

    def flush(self):
        if self._buffer:
            line = self._buffer.strip()
            self._buffer = ""
            if line:
                self._process_line(line)
