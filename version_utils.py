# version_utils.py
import json
import os
import re
import logging
from typing import Literal, TypedDict, Union
from json.decoder import JSONDecodeError


class VersionInfo(TypedDict):
    """版本信息数据结构"""

    current: str
    remote: str
    default: str
    oa_token: str
    bh_ver: str


VersionKey = Literal["current", "remote", "default", "oa_token", "bh_ver", "all"]


class VersionManager:
    VERSION_CONFIG_PATH = "./updates/version.json"
    CHANGE_LOG_PATH = "./updates/changelog.txt"

    # 类常量定义
    CURRENT_VERSION = "1.3.1"  # 硬编码当前版本
    DEFAULT_VERSION = "0.0.0"  # 默认版本
    DEFAULT_OATOKEN = "e257aaa274fb2239094cbe64d9f5ee3e"  # v8.4版本的oa_token
    DEFAULT_BHVER = "8.4.0"  # 默认游戏版本号

    def __init__(self):
        # 实例变量初始化
        self.remote_version = self._load_version_from_file()
        self.oa_token, self.bh_ver = self._load_oa_info_from_file()

        # 缓存版本信息字典
        self._version_info_cache = self._build_version_info()

    def _build_version_info(self) -> VersionInfo:
        """构建版本信息字典"""
        return {
            "current": self.CURRENT_VERSION,
            "remote": self.remote_version,
            "default": self.DEFAULT_VERSION,
            "oa_token": self.oa_token,
            "bh_ver": self.bh_ver,
        }

    def _load_version_from_file(self) -> str:
        """从version.json加载远程版本"""
        try:
            if os.path.exists(self.VERSION_CONFIG_PATH):
                with open(self.VERSION_CONFIG_PATH) as f:
                    data = json.load(f)
                    return data.get("app_info", {}).get("version", self.DEFAULT_VERSION)
            return self.DEFAULT_VERSION
        except (JSONDecodeError, IOError) as e:
            logging.warning(f"读取版本文件失败: {e}")
            return self.DEFAULT_VERSION

    def _load_oa_info_from_file(self) -> tuple[str, str]:
        """从version.json读取oa_token和bh_ver"""
        try:
            if os.path.exists(self.VERSION_CONFIG_PATH):
                with open(self.VERSION_CONFIG_PATH) as f:
                    data = json.load(f)
                    oa_token = data.get("oa_info", {}).get(
                        "oa_token", self.DEFAULT_OATOKEN
                    )
                    bh_ver = data.get("oa_info", {}).get("bh_ver", self.DEFAULT_BHVER)
                    return oa_token, bh_ver
            return self.DEFAULT_OATOKEN, self.DEFAULT_BHVER
        except (JSONDecodeError, IOError) as e:
            logging.warning(f"读取OA信息失败: {e}")
            return self.DEFAULT_OATOKEN, self.DEFAULT_BHVER

    def get_version_info(self, key: VersionKey = "all") -> Union[str, VersionInfo]:
        """
        获取版本相关信息

        :param key: 查询键值，支持:
            'current' - 当前程序版本
            'remote' - 远程版本
            'default' - 默认版本
            'oa_token' - OA令牌
            'bh_ver' - 游戏版本
            'all' - 返回全部版本信息字典
        :return: 请求的版本信息
        """
        if key == "all":
            return self._version_info_cache

        if key in self._version_info_cache:
            return self._version_info_cache[key]

        raise ValueError(f"无效的版本信息键: {key}")

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

    def read_changelog(self) -> str:
        """读取更新日志文件并返回其内容"""
        try:
            with open(self.CHANGE_LOG_PATH, "r", encoding="utf-8") as file:
                return file.read()
        except FileNotFoundError:
            return f"[ERROR] 更新日志文件未找到: {self.CHANGE_LOG_PATH}"
        except Exception as e:
            return f"[ERROR] 读取更新日志失败: {e}"

    def refresh_remote_version(self) -> bool:
        """刷新远程版本信息"""
        try:
            new_version = self._load_version_from_file()
            if new_version != self.remote_version:
                self.remote_version = new_version
                self._version_info_cache["remote"] = new_version
                return True
            return False
        except Exception as e:
            logging.warning(f"刷新远程版本失败: {e}")
            return False

    def refresh_oa_info(self) -> bool:
        """刷新OA令牌和游戏版本信息"""
        try:
            new_oa_token, new_bh_ver = self._load_oa_info_from_file()
            if new_oa_token != self.oa_token or new_bh_ver != self.bh_ver:
                self.oa_token = new_oa_token
                self.bh_ver = new_bh_ver
                self._version_info_cache["oa_token"] = new_oa_token
                self._version_info_cache["bh_ver"] = new_bh_ver
                return True
            return False
        except Exception as e:
            logging.warning(f"刷新OA信息失败: {e}")
            return False


# 全局实例
version_manager = VersionManager()
