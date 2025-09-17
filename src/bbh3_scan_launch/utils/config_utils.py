# config_utils.py
import json
import os
import threading
import logging
from json.decoder import JSONDecodeError
from ..constants import CONFIG_FILE_PATH
from .exception_utils import handle_exceptions

# 延迟导入，避免循环依赖
_version_manager = None
_network_manager = None


def _get_version_manager():
    global _version_manager
    if _version_manager is None:
        from .version_utils import version_manager

        _version_manager = version_manager
    return _version_manager


def _get_network_manager():
    global _network_manager
    if _network_manager is None:
        from .network_utils import network_manager

        _network_manager = network_manager
    return _network_manager


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

    def __init__(self):
        self.lock = threading.Lock()
        self.bh_info = {}
        self.data = {}
        self.cap = None
        # 运行期临时覆盖（不落盘，仅当前进程生效）
        self._temp_mode = False
        self._temp_overrides = {}
        # 从权威源获取版本
        self.current_version = _get_version_manager().get_version_info("current")
        # 初始化 oa_token 和 bh_ver 属性
        self.oa_token = None
        self.bh_ver = None
        self.config = self._load_config()

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
        config_path = CONFIG_FILE_PATH

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
                    logging.info("配置文件包含无效字段，正在优化...")
                    with open(config_path, "w") as f:
                        json.dump(merged_config, f, indent=4)

                return merged_config
        except FileNotFoundError:
            # 如果配置文件不存在，创建默认配置文件
            logging.info("配置文件不存在，正在创建默认配置...")
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(self.DEFAULT_CONFIG, f, indent=4)
            return self.DEFAULT_CONFIG.copy()
        except JSONDecodeError as e:
            # 如果JSON格式错误，备份原文件并创建默认配置
            logging.warning(f"配置文件JSON格式错误: {e}，正在创建默认配置...")
            backup_path = config_path + ".backup"
            if os.path.exists(config_path):
                os.rename(config_path, backup_path)
                logging.info(f"原配置文件已备份到: {backup_path}")
            with open(config_path, "w") as f:
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
            config_path = CONFIG_FILE_PATH
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(config_temp, f, indent=4, separators=(",", ": "))
            self.config = config_temp

    def get_config(self, key, default=None):
        """从当前类获取配置文件"""
        return self.config.get(key, default)

    def set_config(self, key, value):
        """临时修改某项配置文件"""
        self.config[key] = value
        self.write_conf(self.config)

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
        # 获取远程版本信息（不保存文件）
        remote_version_info = _get_network_manager().get_remote_version_info(
            source=source
        )
        if not remote_version_info:
            return {"has_update": False, "error": "无法获取远程版本信息"}

        # 比较版本
        current_version = _get_version_manager().get_version_info("current")
        remote_version = remote_version_info.get("app_info", {}).get("version", "0.0.0")

        # 简单版本比较
        def version_tuple(v):
            return tuple(map(int, v.split(".")))

        has_update = version_tuple(remote_version) > version_tuple(current_version)

        result = {
            "has_update": has_update,
            "current_version": current_version,
            "remote_version": remote_version,
        }

        # 只要远程版本不低于当前版本，就更新本地文件
        should_update_files = version_tuple(remote_version) >= version_tuple(
            current_version
        )

        if should_update_files:
            # 更新本地文件（仅在远程版本号大于等于本地时才更新version.json和changelog）
            if not _get_network_manager().fetch_remote_files(
                source=source, should_update_files=True
            ):
                return {"has_update": False, "error": "无法更新本地文件"}

            # 获取下载链接
            download_links = (
                _get_network_manager().source_manager.get_links_by_category(
                    "download_url"
                )
            )
            if download_links:
                # 返回第一个可用的下载链接
                priority = _get_network_manager().source_manager.get_priority_order()
                for source_name in priority:
                    if source_name in download_links:
                        result["download_url"] = download_links[source_name]
                        break

        return result


# 创建配置管理器实例
config_manager = ConfigManager()

# 使用示例 (如果需要独立运行此脚本进行测试)
if __name__ == "__main__":

    # 获取OA Token (现在是动态获取的)
    logging.info(f"OA Token: {config_manager.oa_token}")
    logging.info(f"BH Version: {config_manager.bh_ver}")

    # 检查程序更新 (使用默认源优先级: gitee -> github -> cdn)
    logging.info("--- 使用默认源检查更新 ---")
    update_info = config_manager.check_program_update()
    logging.info(f"Update Info: {update_info}")

    # 检查程序更新 (强制只使用 GitHub)
    logging.info("--- 强制使用 GitHub 检查更新 ---")
    update_info_github = config_manager.check_program_update(source="github")
    logging.info(f"Update Info (GitHub): {update_info_github}")

    # 刷新 OA 信息 (强制只使用 Gitee)
    logging.info("--- 强制使用 Gitee 刷新 OA 信息 ---")
    config_manager.refresh_oa_info(source="gitee")
    logging.info(f"刷新后 OA Token: {config_manager.oa_token}")
    logging.info(f"刷新后 BH Version: {config_manager.bh_ver}")
