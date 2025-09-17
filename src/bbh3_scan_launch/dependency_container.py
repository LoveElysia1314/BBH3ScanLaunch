# -*- coding: utf-8 -*-
"""
依赖注入容器
集中管理全局实例，避免重复导入和循环依赖
"""
from typing import Any, Dict

# 延迟导入，避免循环依赖
_version_manager = None
_config_manager = None
_network_manager = None


def _get_version_manager_instance():
    """获取version_manager实例"""
    global _version_manager
    if _version_manager is None:
        from .utils.version_utils import version_manager

        _version_manager = version_manager
    return _version_manager


def _get_config_manager_instance():
    """获取config_manager实例"""
    global _config_manager
    if _config_manager is None:
        from .utils.config_utils import config_manager

        _config_manager = config_manager
    return _config_manager


def _get_network_manager_instance():
    """获取network_manager实例"""
    global _network_manager
    if _network_manager is None:
        from .utils.network_utils import network_manager

        _network_manager = network_manager
    return _network_manager


class DependencyContainer:
    """依赖注入容器"""

    def __init__(self):
        self._services: Dict[str, Any] = {}

    def get(self, service_name: str) -> Any:
        """获取服务实例"""
        if service_name not in self._services:
            if service_name == "version_manager":
                self._services[service_name] = _get_version_manager_instance()
            elif service_name == "config_manager":
                self._services[service_name] = _get_config_manager_instance()
            elif service_name == "network_manager":
                self._services[service_name] = _get_network_manager_instance()
            else:
                raise ValueError(f"Service '{service_name}' not found in container")
        return self._services[service_name]


# 全局依赖注入容器实例
container = DependencyContainer()


# 便捷访问方法
def get_version_manager():
    """获取版本管理器"""
    return container.get("version_manager")


def get_config_manager():
    """获取配置管理器"""
    return container.get("config_manager")


def get_network_manager():
    """获取网络管理器"""
    return container.get("network_manager")
