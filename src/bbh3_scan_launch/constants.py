# -*- coding: utf-8 -*-
"""
常量定义文件
集中管理项目中使用的常量，避免硬编码和重复定义
"""
import os

# 版本相关常量
CURRENT_VERSION = "0.9.2"  # 当前版本号
DEFAULT_VERSION = "0.0.0"  # 默认版本号
DEFAULT_OATOKEN = "e257aaa274fb2239094cbe64d9f5ee3e"  # 默认OA Token (v8.4版本)

# 游戏相关常量
GAME_WINDOW_TITLE = "崩坏3"  # 游戏窗口标题

# 目录和文件常量
CONFIG_DIR = "config"
UPDATES_DIR = "updates"
RESOURCES_DIR = "resources"
PICTURES_TO_MATCH_DIR = "pictures_to_match"
TEMPLATES_DIR = "templates"

# 文件名常量
CONFIG_FILE = "config.json"
VERSION_FILE = "version.json"
CHANGELOG_FILE = "CHANGELOG.md"

# 路径相关常量
# 配置目录路径
CONFIG_DIR_PATH = os.path.join(os.path.dirname(__file__), "..", "..", CONFIG_DIR)

# 更新目录路径
UPDATES_DIR_PATH = os.path.join(os.path.dirname(__file__), "..", "..", UPDATES_DIR)

# 资源目录路径
RESOURCES_DIR_PATH = os.path.join(os.path.dirname(__file__), "..", "..", RESOURCES_DIR)

# 模板图片目录（用于图像匹配）
TEMPLATE_PICTURES_DIR = os.path.join(RESOURCES_DIR_PATH, PICTURES_TO_MATCH_DIR)

# Flask模板目录（用于Web界面）
TEMPLATE_WEB_DIR = os.path.join(RESOURCES_DIR_PATH, TEMPLATES_DIR)

# 配置文件路径
CONFIG_FILE_PATH = os.path.join(CONFIG_DIR_PATH, CONFIG_FILE)

# 版本文件路径
VERSION_FILE_PATH = os.path.join(UPDATES_DIR_PATH, VERSION_FILE)

# 更新日志文件路径
CHANGELOG_FILE_PATH = os.path.join(UPDATES_DIR_PATH, CHANGELOG_FILE)
