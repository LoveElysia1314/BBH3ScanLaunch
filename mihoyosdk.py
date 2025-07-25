# 标准库 imports
import hashlib
import hmac
import json
import time
# 自定义库 imports
from network_utils import sendGet, sendPost, sendGetRaw

url = 'https://api-sdk.mihoyo.com/bh3_cn/combo/granter/login/v2/login'
verifyBody = '{"device":"0000000000000000","app_id":"1","channel_id":"14","data":{},"sign":""}'
verifyData = '{"uid":1,"access_key":"590"}'
scanResultR = '{"device":"0000000000000000","app_id":1,"ts":1637593776681,"ticket":"","payload":{},"sign":""}'
scanPayloadR = '{"raw":"","proto":"Combo","ext":""}'
scanRawR = '{"heartbeat":false,"open_id":"","device_id":"0000000000000000","app_id":"1","channel_id":"14","combo_token":"","asterisk_name":"崩坏3桌面扫码器用户","combo_id":"","account_type":"2"}'
scanExtR = '{"data":{}}'
scanDataR = '{"accountType":"2","accountID":"","accountToken":"","dispatch":{}}'
scanCheckR = '{"app_id":"1","device":"0000000000000000","ticket":"abab","ts":1637593776066,"sign":"abab"}'

local_dispatch = json.loads('{}')
local_bh_ver = '5.8.0'
has_dispatch = False
has_bh_ver = False


def bh3Sign(data):
    """生成崩坏3 API请求的HMAC-SHA256签名"""
    key = '0ebc517adb1b62c6b408df153331f9aa'
    sign = hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
    return sign


def makeSign(data):
    """为API请求数据生成签名并添加到原始数据中"""
    sign = ""
    data2 = ""
    for key in sorted(data):
        if key == 'sign':
            continue
        data2 += f"{key}={data[key]}&"
    data2 = data2.rstrip('&').replace(' ', '')
    sign = bh3Sign(data2)
    data['sign'] = sign
    return data


async def getBHVer(cache_bh_ver=None):
    """获取崩坏3当前版本号（优先使用缓存）"""
    global has_bh_ver, local_bh_ver

    if has_bh_ver:
        return local_bh_ver
    feedback = await sendGet('https://api-v2.scanner.hellocraft.xyz/v4/hi3_version', cache_bh_ver)
    # print('[INFO] 云端版本号')
    if feedback == cache_bh_ver:
        local_bh_ver = cache_bh_ver['bh_ver']
        print('[INFO] 获取版本号失败，使用缓存版本号')
    else:
        local_bh_ver = feedback['version']
    has_bh_ver = True
    return local_bh_ver


async def getOAServer(oa_token):
    """获取崩坏3游戏服务器分发信息"""
    global has_dispatch, local_dispatch

    if has_dispatch:
        return local_dispatch

    bh_ver = await getBHVer()
    # timestamp = int(time.time())
    oa_main_url = 'https://outer-dp-bb01.bh3.com/query_gameserver?'
    param = f'version={bh_ver}_gf_android_bilibili&token={oa_token}'
    dispatch = await sendGetRaw(oa_main_url + param, '')

    # print("[DEBUG]", feedback, sep=" ")

    # print("[DEBUG]", dispatch_url, sep=" ")
    # dispatch = await sendOAGet(bh_ver, openid)

    has_dispatch = True

    local_dispatch = dispatch
    # print("[DEBUG]", dispatch, sep=" ")
    return dispatch


async def scanCheck(bh_info, ticket, config):
    """验证崩坏3登录二维码并触发扫码确认"""
    check = json.loads(scanCheckR)
    check['ticket'] = ticket
    check['ts'] = int(time.time())
    check = makeSign(check)
    post_body = json.dumps(check).replace(' ', '')
    feedback = await sendPost('https://api-sdk.mihoyo.com/bh3_cn/combo/panda/qrcode/scan', post_body)
    if feedback['retcode'] != 0:
        print('[INFO] 请求错误！可能是二维码已过期')
        print("[INFO]", feedback)
        return False
    else:
        await scanConfirm(bh_info, ticket, config)


async def scanConfirm(bhinfoR, ticket, config):
    """确认崩坏3二维码扫描并完成登录流程"""
    bhinfo = bhinfoR['data']
    # print("[DEBUG]", bhinfo, sep=" ")
    scan_result = json.loads(scanResultR)
    scan_data = json.loads(scanDataR)
    dispatch = await getOAServer(bhinfo['open_id'])
    scan_data['dispatch'] = dispatch
    scan_data['accountID'] = bhinfo['open_id']
    scan_data['accountToken'] = bhinfo['combo_token']
    scan_ext = json.loads(scanExtR)
    scan_ext['data'] = scan_data
    scan_raw = json.loads(scanRawR)
    scan_raw['open_id'] = bhinfo['open_id']
    scan_raw['combo_id'] = bhinfo['combo_id']
    scan_raw['combo_token'] = bhinfo['combo_token']
    scan_payload = json.loads(scanPayloadR)
    scan_payload['raw'] = json.dumps(scan_raw)
    scan_payload['ext'] = json.dumps(scan_ext)
    scan_result['payload'] = scan_payload
    scan_result['ts'] = int(time.time())
    scan_result['ticket'] = ticket
    scan_result = makeSign(scan_result)
    post_body = json.dumps(scan_result).replace(' ', '')
    # print("[DEBUG]", post_body, sep=" ")
    feedback = await sendPost('https://api-sdk.mihoyo.com/bh3_cn/combo/panda/qrcode/confirm', post_body)
    if feedback['retcode'] == 0:
        print('[INFO] 扫码成功！')
        return True
            
    else:
        print('[INFO] 扫码失败！')
        print("[INFO]", feedback)
        return False


async def verify(uid, access_key):
    """验证B站账号并获取崩坏3登录令牌"""
    print("[DEBUG]", f'verify with uid={uid}', sep=" ")
    data = json.loads(verifyData)
    data['uid'] = uid
    data['access_key'] = access_key
    body = json.loads(verifyBody)
    body['data'] = json.dumps(data)
    # print("[DEBUG]", json.dumps(body, sep=" "))
    body = makeSign(body)
    # print("[DEBUG]", json.dumps(body, sep=" "))
    feedback = await sendPost(url, json.dumps(body).replace(' ', ''))
    return feedback
