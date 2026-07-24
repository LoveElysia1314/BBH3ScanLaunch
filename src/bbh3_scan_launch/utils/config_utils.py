# config_utils.py
import json
import shutil
import threading
import logging
from pathlib import Path
from json.decoder import JSONDecodeError
from ..constants import (
    CONFIG_FILE,
    LEGACY_CONFIG_FILE_PATH,
    get_user_data_dir,
)


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
        "account_login": False,
        "clip_check": False,
        "auto_close": False,
        "auto_clip": False,
        "auto_click": False,
        "debug_print": False,
        "download_priority": ["gitee", "github"],
        # 注意：oa_token 和 bh_ver 不再存储在 config.json 中，
        # 而是每次启动或检查更新时从 version.json 获取
    }

    def __init__(self, config_path=None, legacy_paths=None):
        self.lock = threading.Lock()
        self.bh_info = {}
        self.data = {}
        self.cap = None
        self.config_path = Path(config_path or Path(get_user_data_dir()) / CONFIG_FILE)
        self.legacy_paths = tuple(
            Path(path)
            for path in (
                legacy_paths if legacy_paths is not None else (LEGACY_CONFIG_FILE_PATH,)
            )
        )
        # 运行期临时覆盖（不落盘，仅当前进程生效）
        self._temp_mode = False
        self._temp_overrides = {}
        self._migrate_legacy_config()
        self.config = self._load_config()

    def _migrate_legacy_config(self):
        """首次使用用户数据目录时复制旧安装目录中的配置。"""
        if self.config_path.exists():
            return
        for legacy_path in self.legacy_paths:
            if not legacy_path.is_file() or legacy_path == self.config_path:
                continue
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_path, self.config_path)
                logging.info(
                    "已迁移旧版配置: %s -> %s",
                    legacy_path,
                    self.config_path,
                )
                return
            except OSError:
                logging.exception("迁移旧版配置失败: %s", legacy_path)

    # ---------------- 运行期临时配置覆盖（避免误持久化） ----------------
    def begin_temp_overrides(self, overrides: dict):
        """
        启用临时覆盖：仅在内存中生效，不修改 self.config，不写入磁盘。
        仅接受 DEFAULT_CONFIG 中定义的键。
        """
        if not isinstance(overrides, dict):
            return
        self._temp_overrides = {
            k: v for k, v in overrides.items() if k in self.DEFAULT_CONFIG
        }
        self._temp_mode = True

    def clear_temp_overrides(self):
        """关闭临时覆盖，恢复为纯 self.config 视图"""
        self._temp_overrides.clear()
        self._temp_mode = False

    def get_effective_config(self) -> dict:
        """
        获取“有效配置”视图：
        - 在 temp_mode 下 = config + overrides 的合并视图；
        - 非 temp_mode 下 = config 本身。
        返回新 dict，调用方修改不会影响内部状态。
        """
        base = self.config.copy()
        if self._temp_mode and self._temp_overrides:
            base.update(self._temp_overrides)
        return base

    def _load_config(self):
        """加载配置文件"""
        config_path = self.config_path

        try:
            with config_path.open(encoding="utf-8") as fp:
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
                    logging.info("配置文件包含无效字段，正在优化...")
                    with config_path.open("w", encoding="utf-8") as f:
                        json.dump(merged_config, f, indent=4)

                return merged_config
        except FileNotFoundError:
            # 如果配置文件不存在，创建默认配置文件
            logging.info("配置文件不存在，正在创建默认配置...")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(self.DEFAULT_CONFIG, f, indent=4)
            return self.DEFAULT_CONFIG.copy()
        except JSONDecodeError as e:
            # 如果JSON格式错误，备份原文件并创建默认配置
            logging.warning(f"配置文件JSON格式错误: {e}，正在创建默认配置...")
            backup_path = config_path.with_suffix(config_path.suffix + ".backup")
            if config_path.exists():
                shutil.move(config_path, backup_path)
                logging.info(f"原配置文件已备份到: {backup_path}")
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(self.DEFAULT_CONFIG, f, indent=4)
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
            config_path = self.config_path
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(config_temp, f, indent=4, separators=(",", ": "))
            self.config = config_temp

    def get_config(self, key, default=None):
        """从当前类获取配置文件"""
        return self.config.get(key, default)

    def set_config(self, key, value):
        """临时修改某项配置文件"""
        self.config[key] = value
        self.write_conf(self.config)
