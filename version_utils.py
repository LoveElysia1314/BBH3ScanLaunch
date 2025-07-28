# version_utils.py
import json
import os
from json.decoder import JSONDecodeError
import datetime

class VersionManager:
    VERSION_CONFIG_PATH = './updates/version.json'
    CHANGE_LOG_PATH = './updates/changelog.txt'
    CURRENT_VERSION = "1.2.4"  # 硬编码当前版本

    def __init__(self):
        self.update_version_file()
    
    @classmethod
    def get_current_version(self):
        """获取当前程序版本（硬编码）"""
        return self.CURRENT_VERSION
    
    @classmethod
    def get_remote_version_info(self):
        """获取远程版本信息"""
        try:
            if os.path.exists(self.VERSION_CONFIG_PATH):
                with open(self.VERSION_CONFIG_PATH) as f:
                    return json.load(f)
        except (JSONDecodeError, IOError) as e:
            print(f'[WARNING] 读取版本文件失败: {e}')
        
        return {"version": self.CURRENT_VERSION}
    
    @classmethod
    def update_version_file(self):
        """初始化时更新版本文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.VERSION_CONFIG_PATH), exist_ok=True)
            
            # 准备版本信息
            version_data = {
                "version": self.CURRENT_VERSION,
                "updated_at": datetime.datetime.now().isoformat()
            }
            
            # 检查是否需要更新文件
            need_update = True
            if os.path.exists(self.VERSION_CONFIG_PATH):
                try:
                    with open(self.VERSION_CONFIG_PATH) as f:
                        existing_data = json.load(f)
                    # 如果版本相同，则不需要更新
                    if existing_data.get("version") == self.CURRENT_VERSION:
                        need_update = False
                    else:
                        # 合并现有数据，但用新的版本号覆盖
                        version_data.update(existing_data)
                        version_data["version"] = self.CURRENT_VERSION
                        version_data["updated_at"] = datetime.datetime.now().isoformat()
                except (JSONDecodeError, IOError):
                    pass  # 如果读取失败，使用默认数据
            
            # 写入版本信息
            if need_update:
                with open(self.VERSION_CONFIG_PATH, 'w') as f:
                    json.dump(version_data, f, indent=2)
                print(f'[INFO] 版本文件已更新为: {self.CURRENT_VERSION}')
            else:
                print(f'[INFO] 版本文件已是最新版本: {self.CURRENT_VERSION}')
            
            return True
            
        except Exception as e:
            print(f'[WARNING] 更新版本文件失败: {e}')
            return False

    def read_changelog(self):
        """
        读取更新日志文件并返回其内容。
        """
        
        try:
            # 使用 'with' 语句打开文件，'r' 表示读取模式，'utf-8' 是常见的文本编码
            with open(self.CHANGE_LOG_PATH, 'r', encoding='utf-8') as file:
                # .read() 方法读取整个文件的内容并返回一个字符串
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

# print(version_manager.read_changelog())
