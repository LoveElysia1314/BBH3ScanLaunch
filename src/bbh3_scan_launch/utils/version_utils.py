# version_utils.py
import json
import os
import re
import logging
from typing import Literal, TypedDict, Union
from json.decoder import JSONDecodeError
from ..constants import (
    CURRENT_VERSION,
    DEFAULT_VERSION,
    DEFAULT_OATOKEN,
    VERSION_FILE_PATH,
    CHANGELOG_FILE_PATH,
)
from .exception_utils import handle_exceptions


class VersionInfo(TypedDict):
    """版本信息数据结构"""

    current: str
    remote: str
    default: str
    oa_versions: dict[str, dict[str, str]]


VersionKey = Literal["current", "remote", "default", "oa_versions", "all"]


class VersionManager:
    # 类常量定义（已移至constants.py）
    CURRENT_VERSION = CURRENT_VERSION  # 当前版本
    DEFAULT_VERSION = DEFAULT_VERSION  # 默认版本
    DEFAULT_OATOKEN = DEFAULT_OATOKEN  # 默认OA Token

    VERSION_CONFIG_PATH = VERSION_FILE_PATH  # 版本配置文件路径
    CHANGE_LOG_PATH = CHANGELOG_FILE_PATH  # 更新日志文件路径
    DEFAULT_BHVER = "8.4.0"  # 默认游戏版本号

    def __init__(self):
        # 实例变量初始化
        self.remote_version = self._load_version_from_file()
        self.oa_versions = self._load_oa_versions_from_file()

        # 缓存版本信息字典
        self._version_info_cache = self._build_version_info()

    def _build_version_info(self) -> VersionInfo:
        """构建版本信息字典"""
        return {
            "current": self.CURRENT_VERSION,
            "remote": self.remote_version,
            "default": self.DEFAULT_VERSION,
            "oa_versions": self.oa_versions,
        }

    def get_version_info(
        self, key: VersionKey
    ) -> Union[str, dict[str, dict[str, str]]]:
        """获取版本信息"""
        if key == "all":
            return self._version_info_cache
        return self._version_info_cache.get(key, "")

    @handle_exceptions("读取版本文件失败", DEFAULT_VERSION)
    def _load_version_from_file(self) -> str:
        """从version.json加载远程版本"""
        with open(self.VERSION_CONFIG_PATH) as f:
            data = json.load(f)
            return data.get("app_info", {}).get("version", self.DEFAULT_VERSION)

    @handle_exceptions("读取OA版本配置失败", {})
    def _load_oa_versions_from_file(self) -> dict[str, dict[str, str]]:
        """从version.json读取oa_versions"""
        if os.path.exists(self.VERSION_CONFIG_PATH):
            with open(self.VERSION_CONFIG_PATH) as f:
                data = json.load(f)
                oa_versions = data.get("oa_versions", {})
                if not oa_versions:
                    # 如果没有oa_versions，尝试从旧格式迁移
                    oa_token = data.get("oa_info", {}).get(
                        "oa_token", self.DEFAULT_OATOKEN
                    )
                    bh_ver = data.get("oa_info", {}).get("bh_ver", self.DEFAULT_BHVER)
                    dispatch = data.get("dispatch", "")
                    oa_versions = {bh_ver: {"oa_token": oa_token, "dispatch": dispatch}}
                return oa_versions
        return {}

    def get_oa_token_for_version(self, bh_ver: str) -> str:
        """根据游戏版本获取对应的oa_token"""
        return self.oa_versions.get(bh_ver, {}).get("oa_token", self.DEFAULT_OATOKEN)

    def get_dispatch_for_version(self, bh_ver: str) -> str:
        """根据游戏版本获取对应的dispatch"""
        return self.oa_versions.get(bh_ver, {}).get("dispatch", "")

    def has_version_support(self, bh_ver: str) -> bool:
        """检查是否支持指定的游戏版本"""
        return bh_ver in self.oa_versions

    def has_update(self) -> bool:
        """检查是否存在新版本"""
        current = self.get_version_info("current")
        remote = self.get_version_info("remote")

        # 将版本字符串转换为数字元组进行比较
        def to_version_tuple(version_str):
            parts = version_str.split(".")
            # 处理版本号位数不一致的情况（如1.2 -> 1.2.0）
            while len(parts) < 3:
                parts.append("0")
            return tuple(map(int, parts))

        return to_version_tuple(remote) > to_version_tuple(current)

    @handle_exceptions("读取更新日志失败", "[ERROR] 读取更新日志失败")
    def read_changelog(self) -> str:
        """读取更新日志文件并返回其内容"""
        with open(self.CHANGE_LOG_PATH, "r", encoding="utf-8") as file:
            return file.read()

    @handle_exceptions("刷新OA信息失败", False)
    def refresh_oa_info(self) -> bool:
        """刷新OA版本信息"""
        new_oa_versions = self._load_oa_versions_from_file()
        if new_oa_versions != self.oa_versions:
            self.oa_versions = new_oa_versions
            self._version_info_cache["oa_versions"] = new_oa_versions
            return True
        return False


# 全局实例
version_manager = VersionManager()
