# -*- coding: utf-8 -*-
"""
常量定义文件
集中管理项目中使用的常量，避免硬编码和重复定义
"""

import os
from pathlib import Path

# 版本相关常量
CURRENT_VERSION = "1.0.0"  # 当前版本号
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
# 应用目录路径
APPLICATION_ROOT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)


def get_user_data_dir() -> str:
    """返回不会随安装目录升级而删除的用户数据目录。"""
    override = os.environ.get("BBH3SCANLAUNCH_DATA_DIR")
    if override:
        return os.path.abspath(os.path.expandvars(override))
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return os.path.join(local_app_data, "BBH3ScanLaunch")
    return str(Path.home() / "AppData" / "Local" / "BBH3ScanLaunch")


# 用户配置保存到 LocalAppData；旧版本曾写入安装目录下的 config。
CONFIG_DIR_PATH = get_user_data_dir()
LEGACY_CONFIG_FILE_PATH = os.path.join(APPLICATION_ROOT_PATH, CONFIG_DIR, CONFIG_FILE)

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
