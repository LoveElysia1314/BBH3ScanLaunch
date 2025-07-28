import asyncio
import ctypes
import webbrowser
from PySide6.QtCore import QThread, Signal
import bsgamesdk
import mihoyosdk
from config_utils import config_manager
from bh3_utils import image_processor, is_game_window_exist, click_center_of_game_window

class LoginThread(QThread):
    update_log = Signal(str)
    login_complete = Signal(bool)  # 登录完成信号，传递成功/失败状态

    async def login(self):
        print("[INFO] 登陆B站账号中...")
        try:
            config = config_manager.config
            if config['last_login_succ']:
                print(f"[INFO] 验证缓存账号 {config['uname']} 中...")
                bs_user_info = await bsgamesdk.getUserInfo(config['uid'], config['access_key'])
                if 'uname' in bs_user_info:
                    print(f"[INFO] 登陆B站账号 {bs_user_info['uname']} 成功！")
                    bs_info = {'uid': config['uid'], 'access_key': config['access_key']}
                else:
                    config.update({'last_login_succ': False, 'uid': '', 'access_key': '', 'uname': ''})
                    config_manager.write_conf(config)
            else:
                print(f"[INFO] 登陆B站账号 {config['account']} 中...")
                bs_info = await bsgamesdk.login(config['account'], config['password'], config_manager.cap)
                if "access_key" not in bs_info:
                    self.handle_login_failure(bs_info)
                    # 发出信号，即使失败也要通知主线程登录流程结束
                    self.login_complete.emit(False)
                    return
                bs_user_info = await bsgamesdk.getUserInfo(bs_info['uid'], bs_info['access_key'])
                print(f"[INFO] 登陆B站账号 {bs_user_info['uname']} 成功！")
                config.update({
                    'uid': bs_info['uid'],
                    'access_key': bs_info['access_key'],
                    'last_login_succ': True,
                    'uname': bs_user_info["uname"]
                })
                config_manager.write_conf(config)
            print("[INFO] 登陆崩坏3账号中...")
            bh_info = await mihoyosdk.verify(bs_info['uid'], bs_info['access_key'])
            config_manager.bh_info = bh_info
            if bh_info['retcode'] != 0:
                print(f"[INFO] 登陆失败！{bh_info}")
                self.login_complete.emit(False)
                return
            print("[INFO] 登陆成功！获取OA服务器信息中...")
            # 获取服务器版本号
            server_bh_ver = await mihoyosdk.getBHVer(config_manager.bh_ver)
            # 检查版本是否匹配
            if server_bh_ver != config_manager.bh_ver:
                print(f"[INFO] 版本不匹配 (本地: {config_manager.bh_ver}, 服务器: {server_bh_ver})，更新oa_token.json...")
                if config_manager.download_oa_token():
                    # 重新加载oa_token
                    config_manager.oa_token, config_manager.bh_ver = config_manager._load_oa_token()
                    print(f"[INFO] 已更新oa_token.json (新版本: {config_manager.bh_ver})")
                else:
                    print("[WARNING] oa_token.json更新失败，使用现有版本")
            print(f"[INFO] 当前崩坏3版本: {config_manager.bh_ver}")
            # 使用更新后的oa_token
            oa = await mihoyosdk.getOAServer(config_manager.oa_token)
            if len(oa) < 100:
                print("[INFO] 获取OA服务器失败！请检查Token后重试")
                self.login_complete.emit(False)
                return
            print("[INFO] 获取OA服务器成功！")
            config['account_login'] = True
            config_manager.write_conf(config)
            self.login_complete.emit(True)
        except Exception as e:
            print(f"[ERROR] 登陆过程中发生错误: {str(e)}")
            self.login_complete.emit(False)

    def handle_login_failure(self, bs_info):
        if 'message' in bs_info:
            print("[INFO] 登陆失败！")
            if bs_info['message'] == 'PWD_INVALID':
                print("[INFO] 账号或密码错误！")
            else:
                print(f"[INFO] 原始返回：{bs_info['message']}")
        if 'need_captch' in bs_info:
            print("[INFO] 需要验证码！请打开下方网址进行操作！")
            print(f"[INFO] {bs_info['cap_url']}")
            webbrowser.open_new(bs_info['cap_url'])
        else:
            print(f"[INFO] 登陆失败！{bs_info}")

    def run(self):
        asyncio.run(self.login())

class ParseThread(QThread):
    update_log = Signal(str)
    exit_app = Signal()

    def is_admin(self):
        """使用Windows API检查管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    async def check(self):
        while True:
            config = config_manager.config
            if config['auto_click']:
                if not self.is_admin():
                    print("[INFO] 没有管理员权限，跳过图形识别和点击")
                elif is_game_window_exist():
                    image_processor.match_and_click()
                else:
                    pass
            if config['auto_clip']:
                try:
                    if not is_game_window_exist():
                        await asyncio.sleep(config['sleep_time'])
                        continue
                    screenshot = image_processor.capture_screen()
                    if screenshot is None:
                        await asyncio.sleep(config['sleep_time'])
                        continue
                    qr_parsed = await image_processor.parse_qr_code(
                        image_source='game_window',
                        config=config,
                        bh_info=config_manager.bh_info
                    )
                    if qr_parsed:
                        if config['auto_click']:
                            print('[INFO] 扫码成功，4秒后将自动点击窗口中心')
                            await asyncio.sleep(4)
                            click_center_of_game_window()
                        if config['auto_close']:
                            print('[INFO] 已启用自动退出，2秒后将关闭扫码器')
                            await asyncio.sleep(2)
                            self.exit_app.emit()
                            return
                except Exception as e:
                    print(f"[ERROR] 自动截屏时出错: {str(e)}")
            if config['clip_check'] and config.get('account_login', False):
                await image_processor.parse_qr_code(
                    image_source='clipboard',
                    config=config,
                    bh_info=config_manager.bh_info
                )
            await asyncio.sleep(config['sleep_time'])

    def run(self):
        asyncio.run(self.check())