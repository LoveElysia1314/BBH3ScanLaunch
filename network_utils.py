import asyncio
import hmac
import hashlib
import requests
import time

# 使用标准 print 输出日志
def print_log(msg, level="INFO"):
    print(f"[{level}] {msg}")

async def sendPost(target, data, noReturn=False):
    try:
        session = requests.Session()
        session.trust_env = False
        res = session.post(url=target, data=data)
        if noReturn:
            return
        if res is None:
            print_log("请求错误，正在重试...", "DEBUG")
            return await sendPost(target, data, noReturn)
        return res.json()
    except Exception as e:
        print_log(f"POST 请求失败: {e}", "DEBUG")
        return None

async def sendGet(target, default_ret=None):
    try:
        session = requests.Session()
        session.trust_env = False
        res = session.get(url=target)
        if res is None:
            print_log("请求错误，正在重试...", "DEBUG")
            return await sendGet(target, default_ret)
        return res.json()
    except Exception as e:
        print_log(f"GET 请求失败: {e}", "DEBUG")
        return default_ret

async def sendGetRaw(target, default_ret=None):
    try:
        session = requests.Session()
        session.trust_env = False
        res = session.get(url=target)
        if res is None:
            print_log("请求错误，正在重试...", "DEBUG")
            return await sendGetRaw(target, default_ret)
        return res.text
    except Exception as e:
        print_log(f"GET 原始请求失败: {e}", "DEBUG")
        return default_ret

async def sendBiliPost(url, data):
    header = {
        "User-Agent": "Mozilla/5.0 BSGameSDK",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": "line1-sdk-center-login-sh.biligame.net"
    }
    try:
        session = requests.Session()
        session.trust_env = False
        res = session.post(url=url, data=data, headers=header)
        if res is None:
            print_log("请求错误，3s后重试...", "DEBUG")
            await asyncio.sleep(3)
            return await sendBiliPost(url, data)
        print(res.json())
        return res.json()
    except Exception as e:
        print_log(f"B站POST请求失败: {e}", "DEBUG")
        return None