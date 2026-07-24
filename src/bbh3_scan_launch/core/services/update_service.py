# -*- coding: utf-8 -*-
"""更新服务：封装检查更新与下载的业务入口。"""

from ...utils.version_utils import parse_version


class UpdateService:
    """集中管理远程版本检查、元数据刷新与下载源选择。"""

    def __init__(self, version_manager, network_manager):
        self._version_manager = version_manager
        self._network_manager = network_manager

    def check_update(self, source=None):
        remote_info = self._network_manager.get_remote_version_info(source=source)
        if not remote_info:
            return {"has_update": False, "error": "无法获取远程版本信息"}

        current_version = self._version_manager.get_version_info("current")
        remote_version = remote_info.get("app_info", {}).get("version", "0.0.0")
        current = parse_version(current_version)
        remote = parse_version(remote_version)
        result = {
            "has_update": remote > current,
            "current_version": current_version,
            "remote_version": remote_version,
        }

        if remote < current:
            return result

        if not self._network_manager.fetch_remote_files(
            source=source, should_update_files=True
        ):
            return {"has_update": False, "error": "无法更新本地文件"}

        download_links = self._network_manager.source_manager.get_links_by_category(
            "download_url"
        )
        for source_name in self._network_manager.source_manager.get_priority_order():
            if source_name in download_links:
                result["download_url"] = download_links[source_name]
                break
        return result

    def open_best_download(self, source_priority=None):
        return self._network_manager.try_download_by_priority(source_priority)
