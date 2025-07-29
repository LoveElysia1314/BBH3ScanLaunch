# version_utils.py
import json
import os
from json.decoder import JSONDecodeError

class VersionManager:
    VERSION_CONFIG_PATH = './updates/version.json'
    CHANGE_LOG_PATH = './updates/changelog.txt'
    CURRENT_VERSION = "1.3.0"  # 硬编码当前版本
    REMOTE_VERSION = "0.0.0"  # 远程版本
    DEFAULT_VERSION = "0.0.0"  # 默认版本

    def __init__(self):
        self.REMOTE_VERSION = self._load_version_from_file()
    
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
        return self.CURRENT_VERSION

    def has_update(self):
        """检查是否存在新版本"""
        # 将版本字符串转换为数字元组
        def to_version_tuple(version_str):
            parts = version_str.split('.')
            # 处理版本号位数不一致的情况（如1.2 -> 1.2.0）
            while len(parts) < 3:
                parts.append('0')
            return tuple(map(int, parts))
        
        current_ver = to_version_tuple(self.CURRENT_VERSION)
        remote_ver = to_version_tuple(self.REMOTE_VERSION)
        
        return remote_ver > current_ver
    
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