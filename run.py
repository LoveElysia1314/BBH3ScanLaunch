#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BBH3ScanLaunch 主入口文件
"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# 导入主模块
from bbh3_scan_launch.main import main

if __name__ == "__main__":
    main()
