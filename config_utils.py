# config_utils.py
import json
import os
import threading
from json.decoder import JSONDecodeError
import requests
from urllib.parse import urlparse
import concurrent.futures
import time

class ConfigManager:
    # 默认配置模板（移除了oa_token、bh_ver和ver字段）
    DEFAULT_CONFIG = {
        "account": "",
        "password": "",
        "sleep_time": 1,
        "clip_check": False,
        "auto_close": False,
        "uid": 0,
        "access_key": "",
        "last_login_succ": False,
        "uname": "",
        "auto_clip": False,
        "game_path": "",
        "auto_click": False
    }

    def __init__(self):
        self.lock = threading.Lock()
        self.m_cast_group_ip = '239.0.1.255'
        self.oa_token_path = './oa_token.json'  # 文件名改为oa_token.json
        self.m_cast_group_port = 12585
        self.bh_info = {}
        self.data = {}
        self.cap = None
        
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
                
                return merged_config
                
        except (JSONDecodeError, FileNotFoundError) as e:
            print(f'[WARNING] 配置文件错误: {e}，使用默认配置')
            self.write_conf()
            return self.DEFAULT_CONFIG.copy()

    def write_conf(self, old=None):
        """写入配置文件（过滤掉oa_token和bh_ver）"""
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
        """并行下载oa_token.json文件，选择最快的可用源"""
        print(f'[INFO] 开始下载文件\"oa_token.json\"')
        original_url = "https://cdn.jsdelivr.net/gh/LoveElysia1314/BBH3ScanLaunch@main/oa_token.json"
        mirrors = [
            "https://cdn.jsdelivr.net",
            "https://gcore.jsdelivr.net",
            "https://fastly.jsdelivr.net",
            "https://jsd.onmicrosoft.cn",
            "https://jsd.cdn.zzko.cn"
        ]
        
        def fetch_mirror(mirror_url):
            try:
                start_time = time.time()
                response = requests.get(
                    mirror_url,
                    timeout=2,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if response.status_code == 200:
                    return {
                        'url': mirror_url,
                        'content': response.content,
                        'time': time.time() - start_time,
                        'success': True
                    }
            except Exception:
                pass
            return {'url': mirror_url, 'success': False}
        
        mirror_urls = [f"{mirror}{urlparse(original_url).path}" for mirror in mirrors]
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(fetch_mirror, url) for url in mirror_urls]
            results = []
            
            for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                result = future.result()
                if not result['success']:
                    continue
                
                results.append(result)
                # 只要有一个成功就立即使用最快的
                if results:
                    fastest = min(results, key=lambda x: x['time'])
                    with open(self.oa_token_path, 'wb') as f:
                        f.write(fastest['content'])
                    print(f'[INFO] 使用源: {fastest["url"]}')
                    print(f'[INFO] 文件已保存: {self.oa_token_path}')
                    return True
        
        print('[WARNING] 所有源均无法访问，下载文件\"oa_token.json\"失败')
        return False
    
