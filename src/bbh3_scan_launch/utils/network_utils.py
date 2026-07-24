# network_utils.py
import requests
import os
import webbrowser
import json
import logging
from typing import Callable, Dict, List
from ..constants import VERSION_FILE_PATH
from .exception_utils import handle_exceptions


class SourceManager:
    """管理源配置，完全基于version.json"""

    def __init__(self, priority_provider: Callable[[], list[str]] | None = None):
        self.version_info = None
        self._priority_provider = priority_provider

    def load_version_info(self, version_info):
        """加载版本信息，用于获取sources配置"""
        self.version_info = version_info

    def get_links_by_category(self, category: str) -> Dict[str, str]:
        """根据类别获取所有源的链接"""
        if not self.version_info:
            return {}

        sources = self.version_info.get("sources", {})
        return sources.get(category, {})

    @handle_exceptions("获取下载优先级失败", ["gitee", "github"])
    def get_priority_order(self) -> List[str]:
        """获取源优先级顺序（从config.json读取）"""
        priority = (
            self._priority_provider()
            if self._priority_provider is not None
            else ["gitee", "github"]
        )
        return priority if isinstance(priority, list) else ["gitee", "github"]

    def normalize_source_input(self, source_input):
        """标准化源输入，支持字符串或列表"""
        if isinstance(source_input, str):
            if source_input in ["gitee", "github"]:
                return [source_input]
            return self.get_priority_order()
        elif isinstance(source_input, list):
            return [s for s in source_input if s in ["gitee", "github"]]
        else:
            return self.get_priority_order()


class NetworkManager:
    def __init__(self, priority_provider: Callable[[], list[str]] | None = None):
        self.source_manager = SourceManager(priority_provider)
        self.version_info = None
        self._fallback_version_urls = {
            "gitee": "https://gitee.com/LoveElysia1314/BBH3ScanLaunch/raw/main/updates/version.json",
            "github": "https://raw.githubusercontent.com/LoveElysia1314/BBH3ScanLaunch/main/updates/version.json",
        }
        # 启动时先加载本地版本信息作为配置基础
        self._load_local_version_info()

    def _build_version_url_list(self, source=None):
        """构建按优先级排序的 version.json 获取地址列表"""
        source_priority = self.source_manager.normalize_source_input(source)
        version_urls = []
        version_sources = self.source_manager.get_links_by_category("version_url")

        if version_sources:
            logging.debug("使用本地配置的version.json获取源")
            source_candidates = version_sources
            source_type = "configured"
        else:
            logging.warning("本地配置中无version_url源，使用硬编码回退逻辑")
            source_candidates = self._fallback_version_urls
            source_type = "hardcoded"

        for source_name in source_priority:
            if source_name in source_candidates:
                version_urls.append(
                    {
                        "name": source_name,
                        "url": source_candidates[source_name],
                        "type": source_type,
                    }
                )

        return version_urls

    @handle_exceptions("加载本地版本配置失败", None)
    def _load_local_version_info(self):
        """加载本地打包的version.json作为配置基础"""
        local_version_path = VERSION_FILE_PATH
        if os.path.exists(local_version_path):
            with open(local_version_path, "r", encoding="utf-8") as f:
                local_version_info = json.load(f)
                # 将本地版本信息作为配置基础加载到源管理器
                self.source_manager.load_version_info(local_version_info)
                logging.debug("已加载本地版本配置")
                return local_version_info
        return None

    @handle_exceptions("网络请求失败", {"success": False})
    def fetch_from_source(self, url, timeout=5):
        """从单个源获取数据"""
        logging.debug(f"网络工具GET请求 - URL: {url}")
        response = requests.get(
            url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}
        )
        response.raise_for_status()  # 自动检查HTTP状态码
        return {
            "text": response.text,
            "success": True,
            "status_code": response.status_code,
        }

    def save_to_local(self, content, file_path):
        """保存内容到本地文件"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            logging.error(f"保存文件失败: {str(e)}")
            return False

    def get_remote_version_info(self, source=None):
        """获取远程版本信息，但不保存到本地文件"""
        try:
            version_urls = self._build_version_url_list(source=source)

            # 获取远程version.json（不保存）
            for source_info in version_urls:
                result = self.fetch_from_source(source_info["url"], timeout=10)
                if result and result["success"]:
                    remote_version_info = json.loads(result["text"])
                    logging.info(
                        f"成功从 {source_info['name']} 获取远程版本信息 ({source_info['type']})"
                    )
                    return remote_version_info

            return None
        except Exception as e:
            logging.error(f"获取远程版本信息失败: {str(e)}")
            return None

    def fetch_remote_files(self, source=None, should_update_files=True):
        """从远程获取version.json和CHANGELOG.md（仅在should_update_files为True时才更新）"""
        try:
            source_priority = self.source_manager.normalize_source_input(source)
            version_urls = self._build_version_url_list(source=source)

            # 获取远程version.json
            for source_info in version_urls:
                result = self.fetch_from_source(source_info["url"], timeout=10)
                if result and result["success"]:
                    self.version_info = json.loads(result["text"])
                    # 更新源管理器的配置（使用最新的远程配置）
                    self.source_manager.load_version_info(self.version_info)
                    if should_update_files:
                        self.save_to_local(result["text"], "updates/version.json")
                    break

            # 获取CHANGELOG.md（仅在should_update_files为True时才更新）
            if should_update_files and self.version_info:
                changelog_links = self.source_manager.get_links_by_category("changelog")
                for source_name in source_priority:
                    if source_name in changelog_links:
                        url = changelog_links[source_name]
                        result = self.fetch_from_source(url, timeout=10)
                        if result and result["success"]:
                            self.save_to_local(result["text"], "updates/CHANGELOG.md")
                            break

            return True
        except Exception as e:
            logging.error(f"获取远程文件失败: {str(e)}")
            return False

    def get_download_links(self, source_priority=None):
        """获取下载链接，按优先级排序"""
        if not self.version_info:
            return []

        source_priority = self.source_manager.normalize_source_input(source_priority)
        download_links = self.source_manager.get_links_by_category("download_url")

        urls = []
        for source_name in source_priority:
            if source_name in download_links:
                urls.append(
                    {
                        "name": source_name,
                        "url": download_links[source_name],
                        "type": "download",
                    }
                )
        return urls

    def try_download_by_priority(self, source_priority=None):
        """按优先级尝试下载，失败自动切换下一个源"""
        candidates = self.get_download_links(source_priority)

        if not candidates:
            logging.error("没有可用的下载链接")
            return False

        for candidate in candidates:
            try:
                logging.info(f"尝试从 {candidate['name']} 下载: {candidate['url']}")
                webbrowser.open(candidate["url"])
                return True
            except Exception as e:
                logging.warning(f"从 {candidate['name']} 下载失败: {e}")
                continue

        logging.error("所有下载源均不可用")
        return False
