# version_utils.py
import json
import os
from json.decoder import JSONDecodeError
import datetime

class VersionManager:
    VERSION_CONFIG_PATH = './updates/version.json'
    CHANGE_LOG_PATH = './updates/changelog.txt'
    CURRENT_VERSION = "1.2.5"  # 硬编码当前版本
    DEFAULT_VERSION = "0.0.0"  # 默认版本

    def __init__(self):
        self._current_version = self._load_version_from_file()
    
    def _load_version_from_file(self):
        """从version.json加载当前版本"""
        try:
            if os.path.exists(self.VERSION_CONFIG_PATH):
                with open(self.VERSION_CONFIG_PATH) as f:
                    data = json.load(f)
                    return data.get("app_info", {}).get("version", self.DEFAULT_VERSION)
        except (JSONDecodeError, IOError) as e:
            print(f'[WARNING] 读取版本文件失败: {e}')
        
        return self.DEFAULT_VERSION

    def get_current_version(self):
        """获取当前程序版本"""
        return self._current_version
    
    def read_changelog(self):
        """
        读取更新日志文件并返回其内容。
        """
        try:
            with open(self.CHANGE_LOG_PATH, 'r', encoding='utf-8') as file:
                content = file.read()
                return content
        except FileNotFoundError:
            print(f"[ERROR] 文件未找到: {self.CHANGE_LOG_PATH}")
            return "更新日志文件不存在。"
        except Exception as e:
            print(f"[ERROR] 读取文件时发生错误: {e}")
            return f"无法读取更新日志: {e}"

# 全局实例
version_manager = VersionManager()