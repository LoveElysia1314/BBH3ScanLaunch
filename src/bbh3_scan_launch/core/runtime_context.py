# -*- coding: utf-8 -*-
"""应用运行时上下文。"""

from dataclasses import dataclass

from ..utils.config_utils import ConfigManager
from ..utils.network_utils import NetworkManager
from ..utils.version_utils import VersionManager
from .bh3_utils import BH3GameManager, ImageProcessor
from .game_window import GameWindowService
from .services import AuthService, UpdateService


@dataclass(frozen=True)
class RuntimeContext:
    """跨模块共享的运行时服务集合。"""

    config_manager: object
    network_manager: object
    version_manager: object
    game_manager: object
    image_processor: object
    auth_service: object
    update_service: object

    @classmethod
    def build(cls, notifier=None):
        vm = VersionManager()
        cm = ConfigManager()
        nm = NetworkManager(
            priority_provider=lambda: cm.get_config(
                "download_priority", ["gitee", "github"]
            )
        )
        game_window = GameWindowService(lambda: cm.get_config("game_path", ""))
        gm = BH3GameManager(cm, game_window=game_window, notifier=notifier)
        image_processor = ImageProcessor(game_window=game_window)
        update_service = UpdateService(vm, nm)
        auth_service = AuthService(cm, vm, update_service)
        return cls(
            config_manager=cm,
            network_manager=nm,
            version_manager=vm,
            game_manager=gm,
            image_processor=image_processor,
            auth_service=auth_service,
            update_service=update_service,
        )
