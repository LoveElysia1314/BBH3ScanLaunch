# config_utils.py
import json
import os
import threading
from json.decoder import JSONDecodeError

class ConfigManager:
    # 默认配置模板
    DEFAULT_CONFIG = {
        "account": "",
        "password": "",
        "sleep_time": 1,
        "ver": 6,
        "clip_check": False,
        "auto_close": False,
        "uid": 0,
        "access_key": "",
        "last_login_succ": False,
        "bh_ver": "7.8.0",
        "uname": "",
        "auto_clip": False,
        "oa_token": "ebdda08dce6feb6bc552d393bae58c81",
        "game_path": "",
        "auto_click": False
    }

    def __init__(self):
        self.lock = threading.Lock()  # 线程安全锁
        self.m_cast_group_ip = '239.0.1.255'
        self.m_cast_group_port = 12585
        self.bh_info = {}
        self.data = {}
        self.cap = None
        self.config = self._load_config()

    def _load_config(self):
        """加载配置文件"""
        conf_loop = True
        while conf_loop:
            if not os.path.isfile('./config.json'):
                self.write_conf()
            try:
                with open('./config.json') as fp:
                    loaded_config = json.load(fp)
                    if loaded_config.get('ver', 0) != self.DEFAULT_CONFIG['ver']:
                        print('配置文件已更新，请注意重新修改文件')
                        self.write_conf(loaded_config)
                        continue
            except (JSONDecodeError, FileNotFoundError):
                print('配置文件格式不正确/不存在，重新写入中...')
                self.write_conf()
                continue
            conf_loop = False
        print("配置文件检查完成")
        loaded_config['account_login'] = False
        return loaded_config

    def write_conf(self, old=None):
        """写入配置文件"""
        with self.lock:  # 加锁确保线程安全
            config_temp = dict(self.DEFAULT_CONFIG)  # 深拷贝避免引用共享
            
            if old is not None:
                for key in config_temp:
                    if key in old:
                        config_temp[key] = old[key]
            
            config_temp['ver'] = self.DEFAULT_CONFIG['ver']
            
            with open('./config.json', 'w') as f:
                json.dump(config_temp, f, indent=4, separators=(',', ': '))
            self.config = config_temp  # 同步内存中的配置