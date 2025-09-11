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
