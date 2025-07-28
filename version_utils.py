# version_utils.py
import json
import os
from json.decoder import JSONDecodeError

class VersionManager:
    VERSION_CONFIG_PATH = './updates/version.json'
    CURRENT_VERSION = "1.2.0"  # 硬编码当前版本
    
    @classmethod
    def get_current_version(cls):
        """获取当前程序版本（硬编码）"""
        return cls.CURRENT_VERSION
    
    @classmethod
    def get_remote_version_info(cls):
        """获取远程版本信息"""
        try:
            if os.path.exists(cls.VERSION_CONFIG_PATH):
                with open(cls.VERSION_CONFIG_PATH) as f:
                    return json.load(f)
        except (JSONDecodeError, IOError) as e:
            print(f'[WARNING] 读取版本文件失败: {e}')
        
        return {"version": cls.CURRENT_VERSION}
    
    @classmethod
    def update_version_file(cls):
        """初始化时更新版本文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(cls.VERSION_CONFIG_PATH), exist_ok=True)
            
            # 准备版本信息
            version_data = {
                "version": cls.CURRENT_VERSION,
                "updated_at": __import__('datetime').datetime.now().isoformat()
            }
            
            # 如果文件存在，合并现有数据
            if os.path.exists(cls.VERSION_CONFIG_PATH):
                try:
                    with open(cls.VERSION_CONFIG_PATH) as f:
                        existing_data = json.load(f)
                    version_data.update(existing_data)
                except (JSONDecodeError, IOError):
                    pass  # 如果读取失败，使用默认数据
            
            # 写入版本信息
            with open(cls.VERSION_CONFIG_PATH, 'w') as f:
                json.dump(version_data, f, indent=2)
                
            print(f'[INFO] 版本文件已更新为: {cls.CURRENT_VERSION}')
            return True
            
        except Exception as e:
            print(f'[WARNING] 更新版本文件失败: {e}')
            return False

# 全局实例
version_manager = VersionManager()