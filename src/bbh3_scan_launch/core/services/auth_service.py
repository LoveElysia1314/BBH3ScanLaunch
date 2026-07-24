# -*- coding: utf-8 -*-
"""认证服务：统一处理 B站登录、账号验证与崩坏3 OA 流程。"""

import logging
import webbrowser

from ..sdk import bsgamesdk, mihoyosdk
from ...utils.exception_utils import handle_exceptions


class AuthService:
    """封装登录流程，供后台线程调用。"""

    def __init__(self, config_manager, version_manager, update_service):
        self._config_manager = config_manager
        self._version_manager = version_manager
        self._update_service = update_service
        mihoyosdk.configure_version_manager(version_manager)

    async def authenticate(self) -> bool:
        """执行完整登录流程，返回是否成功。"""
        config = self._config_manager.config
        config_manager = self._config_manager
        version_manager = self._version_manager

        try:
            bs_info = await self._login_with_cache_or_credentials(config)
            if not bs_info:
                return False

            logging.info("登陆崩坏3账号中...")
            bh_info = await mihoyosdk.verify(bs_info["uid"], bs_info["access_key"])
            config_manager.bh_info = bh_info
            if bh_info["retcode"] != 0:
                logging.error(f"登录失败！{bh_info}")
                return False

            logging.info("登录成功，账号：LoveElysia1314，开始获取OA服务器信息...")
            oa_versions = version_manager.get_version_info("oa_versions")
            local_bh_ver = (
                max(oa_versions.keys())
                if oa_versions
                else version_manager.DEFAULT_BHVER
            )
            server_bh_ver = await mihoyosdk.getBHVer(local_bh_ver)
            if server_bh_ver != local_bh_ver:
                logging.warning(
                    f"版本不匹配 (本地: {local_bh_ver}, 服务器: {server_bh_ver})！"
                )

            version_manager.refresh_oa_info()
            if not version_manager.oa_versions:
                update_result = self._update_service.check_update()
                if "error" in update_result:
                    logging.error(
                        "获取远程版本信息失败，无法继续获取OA服务器: "
                        f"{update_result['error']}"
                    )
                    return False
                version_manager.refresh_oa_info()

            if not version_manager.has_version_support(server_bh_ver):
                logging.warning(f"警告：当前配置不支持游戏版本 {server_bh_ver}！")
                logging.warning("请更新 version.json 中的 oa_versions 配置以支持新版本")
                if version_manager.oa_versions:
                    supported_ver = max(version_manager.oa_versions.keys())
                    logging.info(f"将使用支持的版本 {supported_ver} 继续")
                    server_bh_ver = supported_ver
                else:
                    logging.error("无任何支持的版本配置！")
                    return False

            logging.info(f"当前崩坏3版本: {server_bh_ver}")
            oa_token = version_manager.get_oa_token_for_version(server_bh_ver)
            oa = await mihoyosdk.getOAServer(oa_token)
            if len(oa) < 100:
                logging.info("获取OA服务器失败！请检查Token后重试")
                return False

            logging.info("获取OA服务器成功！")
            config["account_login"] = True
            config_manager.write_conf(config)
            return True

        except Exception as exc:
            logging.error(f"认证流程出现异常: {exc}")
            return False

    async def _login_with_cache_or_credentials(self, config):
        """处理账号缓存优先的登录逻辑。"""
        if config.get("last_login_succ"):
            logging.info(f"验证缓存账号 {config['uname']} 中...")
            bs_user_info = await bsgamesdk.getUserInfo(
                config["uid"], config["access_key"]
            )
            if bs_user_info and "uname" in bs_user_info:
                logging.info(f"登陆B站账号 {bs_user_info['uname']} 成功！")
                return {"uid": config["uid"], "access_key": config["access_key"]}

            logging.warning("缓存账号验证失败，将重新登录")
            config.update(
                {
                    "last_login_succ": False,
                    "uid": "",
                    "access_key": "",
                    "uname": "",
                }
            )
            self._config_manager.write_conf(config)

        return await self._login_with_fresh_credentials(config)

    async def _login_with_fresh_credentials(self, config):
        logging.info(f"登陆B站账号 {config['account']} 中...")
        bs_info = await bsgamesdk.login(
            config["account"], config["password"], self._config_manager.cap
        )
        if not bs_info:
            logging.error("登录请求失败，返回结果为空")
            return None
        if "access_key" not in bs_info:
            self._handle_login_failure(bs_info)
            return None

        bs_user_info = await bsgamesdk.getUserInfo(
            bs_info["uid"], bs_info["access_key"]
        )
        if not bs_user_info or "uname" not in bs_user_info:
            logging.error("获取用户信息失败")
            return None

        logging.info(f"重新登陆B站账号 {bs_user_info['uname']} 成功！")
        config.update(
            {
                "uid": bs_info["uid"],
                "access_key": bs_info["access_key"],
                "last_login_succ": True,
                "uname": bs_user_info["uname"],
            }
        )
        self._config_manager.write_conf(config)
        return bs_info

    @handle_exceptions("处理登录失败分支失败", None)
    def _handle_login_failure(self, bs_info):
        if not bs_info:
            logging.error("登录失败：未收到有效的响应数据")
            return

        if self._config_manager.cap is not None and "access_key" not in bs_info:
            logging.info("验证码验证成功，但账号或密码错误！")
            self._config_manager.cap = None
            return

        if bs_info.get("ssl_error"):
            logging.error("网络连接异常，清空账号信息并弹出登录框")
            config = self._config_manager.config
            config.update(
                {
                    "account": "",
                    "password": "",
                    "last_login_succ": False,
                    "uid": "",
                    "access_key": "",
                    "uname": "",
                    "account_login": False,
                }
            )
            self._config_manager.write_conf(config)
            return

        if "message" in bs_info:
            logging.info("登陆失败！")
            if bs_info["message"] == "PWD_INVALID":
                logging.info("账号或密码错误！")
            else:
                logging.info(f"原始返回：{bs_info['message']}")

        if "need_captch" in bs_info:
            logging.info("需要验证码！请打开下方网址进行操作！")
            logging.info(f"{bs_info['cap_url']}")
            webbrowser.open_new(bs_info["cap_url"])
        elif "message" not in bs_info:
            logging.info(f"登陆失败！{bs_info}")
