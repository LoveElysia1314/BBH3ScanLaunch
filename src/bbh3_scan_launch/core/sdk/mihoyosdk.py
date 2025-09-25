# 标准库 imports
import asyncio
import hashlib
import hmac
import json
import requests
import time
import logging

# 本地模块 imports
from ...dependency_container import get_version_manager

version_manager = get_version_manager()

url = "https://api-sdk.mihoyo.com/bh3_cn/combo/granter/login/v2/login"
verifyBody = (
    '{"device":"0000000000000000","app_id":"1","channel_id":"14","data":{},"sign":""}'
)
verifyData = '{"uid":1,"access_key":"590"}'
scanResultR = '{"device":"0000000000000000","app_id":1,"ts":1637593776681,"ticket":"","payload":{},"sign":""}'
scanPayloadR = '{"raw":"","proto":"Combo","ext":""}'
scanRawR = '{"heartbeat":false,"open_id":"","device_id":"0000000000000000","app_id":"1","channel_id":"14","combo_token":"","asterisk_name":"崩坏3桌面扫码器用户","combo_id":"","account_type":"2"}'
scanExtR = '{"data":{}}'
scanDataR = '{"accountType":"2","accountID":"","accountToken":"","dispatch":{}}'
scanCheckR = '{"app_id":"1","device":"0000000000000000","ticket":"abab","ts":1637593776066,"sign":"abab"}'

local_dispatch = json.loads("{}")
local_bh_ver = "5.8.0"
has_dispatch = False
has_bh_ver = False


def bh3Sign(data):
    """生成崩坏3 API请求的HMAC-SHA256签名"""
    key = "0ebc517adb1b62c6b408df153331f9aa"
    sign = hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
    return sign


def makeSign(data):
    """为API请求数据生成签名并添加到原始数据中"""
    sign = ""
    data2 = ""
    for key in sorted(data):
        if key == "sign":
            continue
        data2 += f"{key}={data[key]}&"
    data2 = data2.rstrip("&").replace(" ", "")
    sign = bh3Sign(data2)
    data["sign"] = sign
    return data


async def getBHVer(cache_bh_ver=None):
    """获取崩坏3当前版本号（优先使用缓存）"""
    global has_bh_ver, local_bh_ver

    if has_bh_ver:
        return local_bh_ver
    feedback = await sendGet(
        "https://api-v2.scanner.hellocraft.xyz/v4/hi3_version", cache_bh_ver
    )
    if feedback == cache_bh_ver:
        local_bh_ver = cache_bh_ver["bh_ver"]
        logging.warning("获取版本号失败，使用缓存版本号")
    else:
        local_bh_ver = feedback["version"]
    has_bh_ver = True
    return local_bh_ver


async def getOAServer(oa_token=None):
    """
    获取崩坏3游戏服务器分发信息（dispatch 字段）。

    实现逻辑：
    1. 获取当前游戏版本号
    2. 从 version_manager 中获取对应版本的 dispatch 字段
       若存在且非空，则直接使用并缓存。
    3. 若无预设 dispatch，则使用对应版本的 oa_token 通过 OA 服务器接口获取分发信息：
       - 拼接 OA 服务器接口 https://outer-dp-bb01.bh3.com/query_gameserver?version=xxx&token=oa_token
       - 以 oa_token 作为 token 参数，发起 GET 请求，返回 dispatch 字段内容。
       - 缓存结果。
    4. 若两种方式均不可用，则返回空 JSON 字符串。
    """
    global has_dispatch, local_dispatch

    if has_dispatch:
        return local_dispatch

    # 获取当前游戏版本
    bh_ver = await getBHVer()

    # 方式一：从 version_manager 获取对应版本的 dispatch
    dispatch = version_manager.get_dispatch_for_version(bh_ver)
    if dispatch and dispatch.strip():
        logging.debug(f"从 version.json 获取 {bh_ver} 版本的 dispatch 成功")
        has_dispatch = True
        local_dispatch = dispatch
        return dispatch
    else:
        logging.debug(f"version.json 中无 {bh_ver} 版本的有效 dispatch 字段")

    # 方式二：使用对应版本的 oa_token 通过 OA 服务器接口获取分发信息
    oa_token = version_manager.get_oa_token_for_version(bh_ver)
    if not oa_token:
        logging.error(f"version.json 中无 {bh_ver} 版本的有效 oa_token")
        return "{}"

    oa_main_url = "https://outer-dp-bb01.bh3.com/query_gameserver?"
    param = f"version={bh_ver}_gf_android_bilibili&token={oa_token}"
    dispatch = await sendGetRaw(oa_main_url + param, "")

    has_dispatch = True
    local_dispatch = dispatch
    return dispatch


async def scanCheck(bh_info, ticket, config):
    """验证崩坏3登录二维码并触发扫码确认"""
    check = json.loads(scanCheckR)
    check["ticket"] = ticket
    check["ts"] = int(time.time())
    check = makeSign(check)
    post_body = json.dumps(check).replace(" ", "")
    feedback = await sendPost(
        "https://api-sdk.mihoyo.com/bh3_cn/combo/panda/qrcode/scan", post_body
    )
    if feedback["retcode"] != 0:
        logging.info("请求错误！可能是二维码已过期")
        logging.info(f"{feedback}")
        return False
    else:
        await scanConfirm(bh_info, ticket, config)


async def scanConfirm(bhinfoR, ticket, config):
    """确认崩坏3二维码扫描并完成登录流程"""
    bhinfo = bhinfoR["data"]
    scan_result = json.loads(scanResultR)
    scan_data = json.loads(scanDataR)
    dispatch = await getOAServer(bhinfo["open_id"])
    scan_data["dispatch"] = dispatch
    scan_data["accountID"] = bhinfo["open_id"]
    scan_data["accountToken"] = bhinfo["combo_token"]
    scan_ext = json.loads(scanExtR)
    scan_ext["data"] = scan_data
    scan_raw = json.loads(scanRawR)
    scan_raw["open_id"] = bhinfo["open_id"]
    scan_raw["combo_id"] = bhinfo["combo_id"]
    scan_raw["combo_token"] = bhinfo["combo_token"]
    scan_payload = json.loads(scanPayloadR)
    scan_payload["raw"] = json.dumps(scan_raw)
    scan_payload["ext"] = json.dumps(scan_ext)
    scan_result["payload"] = scan_payload
    scan_result["ts"] = int(time.time())
    scan_result["ticket"] = ticket
    scan_result = makeSign(scan_result)
    post_body = json.dumps(scan_result).replace(" ", "")
    feedback = await sendPost(
        "https://api-sdk.mihoyo.com/bh3_cn/combo/panda/qrcode/confirm", post_body
    )
    if feedback["retcode"] == 0:
        logging.info("扫码成功！")
        return True

    else:
        logging.info("扫码失败！")
        logging.info(f"{feedback}")
        return False


async def verify(uid, access_key):
    """验证B站账号并获取崩坏3登录令牌"""
    logging.debug(f"verify with uid={uid}")
    data = json.loads(verifyData)
    data["uid"] = uid
    data["access_key"] = access_key
    body = json.loads(verifyBody)
    body["data"] = json.dumps(data)
    body = makeSign(body)
    feedback = await sendPost(url, json.dumps(body).replace(" ", ""))
    return feedback


async def sendPost(target, data, noReturn=False):
    logging.debug(f"米哈游POST请求 - URL: {target}")
    logging.debug(f"米哈游POST请求 - 数据: {data}")
    try:
        session = requests.Session()
        res = session.post(url=target, data=data)
        if noReturn:
            return
        if res is None:
            logging.debug("请求错误，正在重试...")
            return await sendPost(target, data, noReturn)
        return res.json()
    except Exception as e:
        logging.error(f"POST 请求失败: {e}")
        return None


async def sendGet(target, default_ret=None):
    logging.debug(f"米哈游GET请求 - URL: {target}")
    try:
        session = requests.Session()
        res = session.get(url=target)
        if res is None:
            logging.debug("请求错误，正在重试...")
            return await sendGet(target, default_ret)
        return res.json()
    except Exception as e:
        logging.error(f"GET 请求失败: {e}")
        return default_ret


async def sendGetRaw(target, default_ret=None):
    logging.debug(f"米哈游GET原始请求 - URL: {target}")
    try:
        session = requests.Session()
        res = session.get(url=target)
        if res is None:
            logging.debug("请求错误，正在重试...")
            return await sendGetRaw(target, default_ret)
        return res.text
    except Exception as e:
        logging.error(f"GET 原始请求失败: {e}")
        return default_ret
