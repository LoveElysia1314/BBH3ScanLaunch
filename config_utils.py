# config_utils.py
import json
import os
import threading
from json.decoder import JSONDecodeError
import requests
from urllib.parse import urlparse
import concurrent.futures
import time
from network_utils import network_manager  # 导入新的网络模块

class ConfigManager:
    # 默认配置模板
    DEFAULT_CONFIG = {
        "game_path": "",
        "sleep_time": 1,
        "account": "",
        "password": "",
        "uid": 0,
        "access_key": "",
        "uname": "",
        "last_login_succ": False,
        "clip_check": False,
        "auto_close": False,
        "auto_clip": False,
        "auto_click": False,
        "debug_print": False,
        "program_version": "1.0.0"  # 添加程序版本字段
    }

    def __init__(self):
        self.lock = threading.Lock()
        self.m_cast_group_ip = '239.0.1.255'
        self.oa_token_path = './oa_token.json'
        self.m_cast_group_port = 12585
        self.bh_info = {}
        self.data = {}
        self.cap = None
        
        # 设置当前程序版本
        network_manager.set_current_version(self.DEFAULT_CONFIG.get("program_version", "1.0.0"))
        
        self._ensure_oa_token_file()
        # 从oa_token.json读取oa_token和bh_ver
        self.oa_token, self.bh_ver = self._load_oa_token()
        self.config = self._load_config()

    def _ensure_oa_token_file(self):
        """确保oa_token.json文件存在"""
        if not os.path.exists(self.oa_token_path):
            print('[INFO] oa_token.json不存在，尝试下载...')
            if not self.download_oa_token():
                print('[WARNING] 下载oa_token.json失败，将使用内置默认值')
                # 创建默认的oa_token.json
                default_oa_token = {"oa_token": "e257aaa274fb2239094cbe64d9f5ee3e", "bh_ver": "8.4.0"}
                with open(self.oa_token_path, 'w') as f:
                    json.dump(default_oa_token, f)

    def _load_oa_token(self):
        """从oa_token.json加载oa_token和bh_ver"""
        try:
            with open(self.oa_token_path) as f:
                oa_config = json.load(f)
                return oa_config.get("oa_token", "e257aaa274fb2239094cbe64d9f5ee3e"), oa_config.get("bh_ver", "8.4.0")
        except (JSONDecodeError, IOError) as e:
            print(f'[WARNING] 读取oa_token.json失败：{e}')
            return "e257aaa274fb2239094cbe64d9f5ee3e", "8.4.0"

    def _load_config(self):
        """加载配置文件"""
        config_path = './config.json'
        
        # 如果配置文件不存在，创建默认配置
        if not os.path.isfile(config_path):
            self.write_conf()
            return self.DEFAULT_CONFIG.copy()
        
        try:
            with open(config_path) as fp:
                loaded_config = json.load(fp)
                
                # 提取有效字段（只保留在DEFAULT_CONFIG中存在的键）
                valid_config = {}
                for key in self.DEFAULT_CONFIG:
                    if key in loaded_config:
                        valid_config[key] = loaded_config[key]
                
                # 合并有效字段和默认配置
                merged_config = self.DEFAULT_CONFIG.copy()
                merged_config.update(valid_config)
                
                # 如果原始配置有无效字段，更新文件
                if loaded_config != merged_config:
                    print('[INFO] 配置文件包含无效字段，正在优化...')
                    with open(config_path, 'w') as f:
                        json.dump(merged_config, f, indent=4)
                
                # 更新网络管理器的版本
                network_manager.set_current_version(merged_config.get("program_version", "1.0.0"))
                
                return merged_config
                
        except (JSONDecodeError, FileNotFoundError) as e:
            print(f'[WARNING] 配置文件错误: {e}，使用默认配置')
            self.write_conf()
            return self.DEFAULT_CONFIG.copy()

    def write_conf(self, old=None):
        """写入配置文件"""
        with self.lock:
            # 从旧配置中提取有效字段
            config_temp = self.DEFAULT_CONFIG.copy()
            if old is not None:
                for key in self.DEFAULT_CONFIG:
                    if key in old:
                        config_temp[key] = old[key]
            
            # 写入配置文件
            with open('./config.json', 'w') as f:
                json.dump(config_temp, f, indent=4, separators=(',', ': '))
            self.config = config_temp

    def download_oa_token(self):
        """下载oa_token.json文件"""
        try:
            # 使用网络管理器的并行下载功能
            oa_token, bh_ver = network_manager.get_oa_token_parallel()
            
            # 更新实例变量
            self.oa_token = oa_token
            self.bh_ver = bh_ver
            
            # 保存到文件
            token_data = {"oa_token": oa_token, "bh_ver": bh_ver}
            with open(self.oa_token_path, 'w') as f:
                json.dump(token_data, f)
                
            return True
        except Exception as e:
            print(f'[ERROR] 下载OA Token失败: {e}')
            return False
    
    def check_program_update(self):
        """检查程序更新"""
        return network_manager.check_program_update()
    
    def download_program_update(self, progress_callback=None):
        """下载程序更新"""
        update_info = self.check_program_update()
        if update_info.get("has_update"):
            return network_manager.download_update(
                update_info["download_url"], 
                progress_callback
            )
        return None
    
    def install_program_update(self, new_file_path):
        """安装程序更新"""
        return network_manager.install_update(new_file_path)
    
    def get_program_version(self):
        """获取当前程序版本"""
        return self.config.get("program_version", "1.0.0")
    
    def set_program_version(self, version_str):
        """设置程序版本"""
        self.config["program_version"] = version_str
        network_manager.set_current_version(version_str)
        self.write_conf(self.config)

# 使用示例
if __name__ == "__main__":
    # 创建配置管理器实例
    config_manager = ConfigManager()
    
    # 获取OA Token
    print("OA Token:", config_manager.oa_token)
    print("BH Version:", config_manager.bh_ver)
    
    # 检查程序更新
    update_info = config_manager.check_program_update()
    print("Update Info:", update_info)