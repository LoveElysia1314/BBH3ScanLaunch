import asyncio
import requests

async def sendPost(target, data, noReturn=False):
    try:
        session = requests.Session()
        session.trust_env = False
        res = session.post(url=target, data=data)
        if noReturn:
            return
        if res is None:
            print("[INFO] 请求错误，正在重试...")
            return await sendPost(target, data, noReturn)
        return res.json()
    except Exception as e:
        print(f"[ERROR] POST 请求失败: {e}")
        return None

async def sendGet(target, default_ret=None):
    try:
        session = requests.Session()
        session.trust_env = False
        res = session.get(url=target)
        if res is None:
            print("[INFO] 请求错误，正在重试...")
            return await sendGet(target, default_ret)
        return res.json()
    except Exception as e:
        print(f"[ERROR] GET 请求失败: {e}")
        return default_ret

async def sendGetRaw(target, default_ret=None):
    try:
        session = requests.Session()
        session.trust_env = False
        res = session.get(url=target)
        if res is None:
            print("[INFO] 请求错误，正在重试...")
            return await sendGetRaw(target, default_ret)
        return res.text
    except Exception as e:
        print(f"[ERROR] GET 原始请求失败: {e}")
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
            print("[INFO] 请求错误，3s后重试...")
            await asyncio.sleep(3)
            return await sendBiliPost(url, data)
        # print("[DEBUG]", res.json(),sep=" ")
        return res.json()
    except Exception as e:
        print(f"[ERROR] B站POST请求失败: {e}")
        return None