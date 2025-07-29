# config_utils.py
import json
import os
import threading
from json.decoder import JSONDecodeError
from version_utils import version_manager
from network_utils import network_manager  # 导入修改后的网络模块

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
        "debug_print": False
        # 注意：oa_token 和 bh_ver 不再存储在 config.json 中，
        # 而是每次启动或检查更新时从 version.json 获取
    }

    def __init__(self):
        self.lock = threading.Lock()
        self.m_cast_group_ip = '239.0.1.255'
        # oa_token.json 已被合并，不再需要此路径
        # self.oa_token_path = r'updates\oa_token.json' 
        self.m_cast_group_port = 12585
        self.bh_info = {}
        self.data = {}
        self.cap = None
        # 从权威源获取版本
        self.current_version = version_manager.get_current_version()
        
        # 初始化时，从网络获取最新的 oa_token 和 bh_ver
        # 不再需要 _ensure_oa_token_file 和 _load_oa_token
        self.oa_token, self.bh_ver = self._fetch_oa_info()
        
        self.config = self._load_config()

    def _fetch_oa_info(self, source=None):
        """从网络获取最新的 oa_token 和 bh_ver"""
        try:
            # 调用修改后的网络管理器方法
            oa_token, bh_ver = network_manager.get_oa_token(source=source)
            print(f'[INFO] 成功获取 OA 信息: Token={oa_token[:8]}..., BH Ver={bh_ver}')
            return oa_token, bh_ver
        except Exception as e:
            print(f'[WARNING] 从网络获取 OA 信息失败: {e}，使用默认值')
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

    # --- 已废弃或修改的方法 ---
    # def _ensure_oa_token_file(self): ...
    # def _load_oa_token(self): ...
    # def download_oa_token(self): ...
    # --------------------------

    # --- 新增或修改的方法 ---
    
    def refresh_oa_info(self, source=None):
        """
        公开方法：刷新 OA Token 和 BH 版本信息。
        可以传递 source 参数来指定数据源。
        """
        self.oa_token, self.bh_ver = self._fetch_oa_info(source=source)
        # 如果需要，可以在这里触发保存到某个临时文件或缓存，
        # 但通常这些信息是每次需要时动态获取的。

    def check_program_update(self, source=None):
        """
        检查程序更新。
        可以传递 source 参数来指定版本信息和文件的来源。
        """
        # 调用修改后的网络管理器方法，并传递 source 参数
        return network_manager.check_program_update(source=source)
    
    def download_program_update(self, progress_callback=None, source=None):
        """
        下载程序更新。
        可以传递 source 参数来指定下载文件的来源。
        """
        update_info = self.check_program_update(source=source) # 也传递 source
        if update_info.get("has_update") and update_info.get("download_url"):
            # 调用修改后的网络管理器方法，并传递 source 参数
            return network_manager.download_update(
                update_info["download_url"], 
                progress_callback,
                source=source # 传递 source 参数给 download_update
            )
        elif update_info.get("has_update"):
             print("[WARNING] 更新信息中缺少 download_url")
        return None
    
    def install_program_update(self, new_file_path):
        """安装程序更新"""
        return network_manager.install_update(new_file_path)
    
    # program_version 相关方法可以保留，但逻辑可能需要调整
    # 如果版本信息完全由 network_utils 管理，这些可能变得不那么重要
    def get_program_version(self):
        """获取当前程序版本"""
        # 优先使用 version_utils 中的版本
        return self.current_version


# 创建配置管理器实例
config_manager = ConfigManager()

# 使用示例 (如果需要独立运行此脚本进行测试)
if __name__ == "__main__":
    
    # 获取OA Token (现在是动态获取的)
    print("OA Token:", config_manager.oa_token)
    print("BH Version:", config_manager.bh_ver)
    
    # 检查程序更新 (使用默认源优先级: gitee -> github -> cdn)
    print("\n--- 使用默认源检查更新 ---")
    update_info = config_manager.check_program_update()
    print("Update Info:", update_info)

    # 检查程序更新 (强制只使用 GitHub)
    print("\n--- 强制使用 GitHub 检查更新 ---")
    update_info_github = config_manager.check_program_update(source='github')
    print("Update Info (GitHub):", update_info_github)

    # 刷新 OA 信息 (强制只使用 Gitee)
    print("\n--- 强制使用 Gitee 刷新 OA 信息 ---")
    config_manager.refresh_oa_info(source='gitee')
    print("刷新后 OA Token:", config_manager.oa_token)
    print("刷新后 BH Version:", config_manager.bh_ver)
