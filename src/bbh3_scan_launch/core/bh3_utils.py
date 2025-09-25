# -*- coding: utf-8 -*-
import os
import re
import time
import numpy as np
import logging
import psutil
import ctypes
from cv2 import matchTemplate, TM_CCOEFF_NORMED, minMaxLoc
from ctypes import windll
from PIL import Image, ImageGrab
import pyautogui
from pyzbar.pyzbar import decode
import win32con
import win32gui
import win32ui
from .sdk import mihoyosdk
from ..constants import GAME_WINDOW_TITLE, TEMPLATE_PICTURES_DIR
from ..utils.exception_utils import handle_exceptions

# 常量定义（已移至constants.py）
TEMPLATE_DIR = TEMPLATE_PICTURES_DIR  # 向后兼容


# 进程检测相关方法
def is_bh3_running():
    """
    检查 BH3.exe 是否正在运行
    """
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == "bh3.exe":
                return True
        except Exception:
            continue
    return False


def kill_bh3():
    """
    结束所有 BH3.exe 进程
    """
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == "bh3.exe":
                proc.kill()
        except Exception:
            continue


def start_bh3(game_path):
    """
    启动 BH3.exe
    """
    if not is_bh3_running():
        os.startfile(game_path)
        return True
    return False


class BH3GameManager:
    """
    崩坏3游戏管理器
    统一管理游戏进程、启动、窗口检测等功能
    """

    def __init__(self):
        self.game_path = None
        self._load_game_path()

    def _load_game_path(self):
        """加载游戏路径配置"""
        from ..utils.config_utils import config_manager

        config = config_manager.config
        self.game_path = config.get("game_path")

    def is_bh3_running(self):
        """
        检查 BH3.exe 是否正在运行
        """
        return is_bh3_running()

    def kill_bh3(self):
        """
        结束所有 BH3.exe 进程
        """
        kill_bh3()

    def start_bh3(self):
        """
        启动 BH3.exe
        """
        if not self.game_path:
            logging.info("请先配置游戏路径！")
            return False
        if not self.is_bh3_running():
            os.startfile(self.game_path)
            logging.info("崩坏3已启动")
            return True
        logging.info("崩坏3已在运行，无需重复启动")
        return False

    def is_game_window_exist(self):
        """检查崩坏3游戏窗口是否存在"""
        return is_game_window_exist()

    def launch_game(self, show_messages=True):
        """
        启动游戏
        """
        if not self.game_path:
            logging.info("请先配置游戏路径！")
            if show_messages:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(None, "路径未配置", "请先配置游戏路径！")
            return False

        # 检查进程，防止重复启动
        if self.is_bh3_running():
            logging.info("崩坏3已在运行，无需重复启动")
            if show_messages:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.information(None, "已在运行", "崩坏3已在运行，无需重复启动")
            return False
        logging.info("正在启动崩坏3...")
        try:
            self.start_bh3()
            logging.info("崩坏3已启动")
            return True
        except Exception as e:
            logging.error(f"启动游戏失败: {e}")
            if show_messages:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(None, "启动失败", f"无法启动游戏: {e}")
            return False

    def one_click_login(self, skip_launch=False, show_messages=True):
        """
        一键登录模式，支持跳过游戏启动（防止重复打开游戏）
        :param skip_launch: 如果为 True，则不执行 launchGame
        :param show_messages: 是否显示消息框
        """
        # 如果不跳过启动，则调用统一的启动方法
        if not skip_launch:
            if not self.launch_game(show_messages=show_messages):
                return False

        # 这里可以添加一键登录的逻辑，但由于依赖UI，可能需要外部处理
        logging.info("一键进入舰桥模式已启用")
        return True

    async def auto_monitor(
        self,
        config,
        image_processor,
        click_center_of_game_window_func,
        exit_app_func=None,
    ):
        """
        自动监控和处理游戏窗口
        :param config: 配置字典
        :param image_processor: ImageProcessor 实例
        :param click_center_of_game_window_func: 点击窗口中心的函数
        :param exit_app_func: 退出应用的函数（可选）
        """
        import asyncio
        import ctypes
        from ..utils.config_utils import config_manager

        while True:
            try:
                # 处理自动点击
                if config.get("auto_click") and self._is_admin():
                    image_processor.match_and_click()
                elif config.get("auto_click") and not self._is_admin():
                    logging.debug("没有管理员权限，跳过图形识别和点击")

                # 处理自动截屏
                if config.get("auto_clip"):
                    screenshot = image_processor.capture_screen()
                    if screenshot:
                        from ..utils.config_utils import config_manager

                        qr_parsed = await image_processor.parse_qr_code(
                            image_source="game_window",
                            config=config,
                            bh_info=config_manager.bh_info,
                        )
                        if qr_parsed:
                            if config.get("auto_click"):
                                logging.info("扫码成功，4秒后将自动点击窗口中心")
                                await asyncio.sleep(4)
                                click_center_of_game_window_func()
                            if config.get("auto_close") and exit_app_func:
                                logging.info("已启用自动退出，2秒后将关闭扫码器")
                                await asyncio.sleep(2)
                                exit_app_func()
                                return

                # 处理剪贴板检查：无论是否开启自动截图，只要已登录就尝试从剪贴板识别二维码
                if config.get("account_login", False):
                    from ..utils.config_utils import config_manager

                    await image_processor.parse_qr_code(
                        image_source="clipboard",
                        config=config,
                        bh_info=config_manager.bh_info,
                    )

                # 根据配置的间隔时间等待
                await asyncio.sleep(config.get("sleep_time", 1))

            except Exception as e:
                logging.error(f"自动监控过程中发生错误: {str(e)}")
                await asyncio.sleep(1)

    def _is_admin(self):
        """检查管理员权限"""
        return ctypes.windll.shell32.IsUserAnAdmin()


@handle_exceptions("检查窗口存在状态出错", False)
def is_game_window_exist():
    """检查崩坏3游戏窗口是否存在"""

    def enum_windows(hwnd, results):
        if (
            win32gui.IsWindowVisible(hwnd)
            and win32gui.GetWindowText(hwnd) == GAME_WINDOW_TITLE
        ):
            results.append(True)

    results = []
    win32gui.EnumWindows(enum_windows, results)
    exist = bool(results)
    return exist


@handle_exceptions("激活窗口出错", False)
def active_game_window():
    """激活崩坏3游戏窗口并置于前台"""
    hwnd = win32gui.FindWindow(None, GAME_WINDOW_TITLE)
    if not hwnd:
        return False

    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.5)

    win32gui.SetForegroundWindow(hwnd)
    return True


def click_center_of_game_window():
    """点击崩坏3游戏窗口中心位置"""
    hwnd = win32gui.FindWindow(None, GAME_WINDOW_TITLE)
    if not hwnd or not is_game_window_exist():
        logging.info("未找到游戏窗口")
        return

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    center_x = left + width // 2
    center_y = top + height // 2

    pyautogui.click(center_x, center_y)


class WindowCapture:
    """
    后台窗口截图工具类
    使用Windows API实现后台窗口截图功能，支持对崩坏3游戏窗口的截图
    """

    def __init__(self, window_title):
        self.window_title = window_title
        self.hwnd = None

    def _find_window(self):
        """查找崩坏3游戏窗口句柄"""
        self.hwnd = win32gui.FindWindow(None, self.window_title)
        if self.hwnd:
            return True
        logging.debug(f"未找到窗口: {self.window_title}")
        return False

    @handle_exceptions("窗口捕获出错", None)
    def capture_window(self):
        """截取整个游戏窗口画面（支持后台窗口）"""
        # 若无句柄或句柄已无效，尝试重新查找
        try:
            hwnd_valid = bool(self.hwnd) and win32gui.IsWindow(self.hwnd)
        except Exception:
            hwnd_valid = False

        if not hwnd_valid and not self._find_window():
            logging.debug("无法获取窗口句柄，截图失败")
            return None

        left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
        # 二次校验：获取窗口矩形失败时，尝试刷新句柄
        try:
            left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
        except Exception:
            if not self._find_window():
                logging.debug("窗口句柄无效且刷新失败，截图终止")
                return None
            left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
        width, height = right - left, bot - top

        hwndDC = None
        mfcDC = None
        saveDC = None
        saveBitMap = None
        try:
            hwndDC = win32gui.GetWindowDC(self.hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 0)
            # PrintWindow 可能在句柄刚失效时返回黑屏；重试一次
            try:
                windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 0)
            except Exception as e:
                logging.debug(f"PrintWindow 调用失败，尝试刷新句柄后重试: {e}")
                if self._find_window():
                    windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 0)

            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)
            pil_img = Image.frombuffer(
                "RGB",
                (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                bmpstr,
                "raw",
                "BGRX",
                0,
                1,
            )
            return pil_img
        except Exception as e:
            logging.error(f"截图过程中出错: {e}")
            return None
        finally:
            # 确保资源被正确释放
            try:
                if saveBitMap:
                    win32gui.DeleteObject(saveBitMap.GetHandle())
            except Exception:
                pass
            try:
                if saveDC:
                    saveDC.DeleteDC()
            except Exception:
                pass
            try:
                if mfcDC:
                    mfcDC.DeleteDC()
            except Exception:
                pass
            try:
                if hwndDC:
                    win32gui.ReleaseDC(self.hwnd, hwndDC)
            except Exception:
                pass


class ImageProcessor:
    """
    图像处理引擎
    提供模板匹配、屏幕捕获和二维码识别功能，用于崩坏3游戏界面识别
    """

    def __init__(self, template_dir=TEMPLATE_DIR):
        logging.info("初始化图像处理器")
        self.template_dir = template_dir
        self.screen_width, self.screen_height = self._get_screen_resolution()
        logging.info(f"屏幕分辨率: {self.screen_width}x{self.screen_height}")
        self.template_cache = {}  # 内存缓存模板
        self.window_capturer = None  # 延迟初始化窗口捕获器
        self._load_templates()

    def _get_screen_resolution(self):
        """获取主屏幕分辨率"""
        return windll.user32.GetSystemMetrics(0), windll.user32.GetSystemMetrics(1)

    def _get_resolution_from_filename(self, filename):
        """从模板文件名中提取分辨率信息"""
        match = re.search(r"(\d+)p", filename)
        return int(match.group(1)) if match else None

    def _load_templates(self):
        """加载模板图片并缩放到当前屏幕分辨率"""
        if not os.path.exists(self.template_dir):
            os.makedirs(self.template_dir, exist_ok=True)
            logging.info(f"已创建模板目录: {self.template_dir}")
            return

        loaded_count = 0
        for filename in os.listdir(self.template_dir):
            if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            file_path = os.path.join(self.template_dir, filename)
            src_resolution = self._get_resolution_from_filename(filename)

            if not src_resolution:
                logging.warning(f"跳过文件（缺少有效分辨率标识）: {filename}")
                continue

            # logging.debug(f"加载模板: {filename} (源分辨率: {src_resolution}p)")
            try:
                # 使用PIL代替cv2加载和缩放模板
                template_img = Image.open(file_path).convert("L")
                scale_factor = self.screen_height / src_resolution
                new_width = int(template_img.width * scale_factor)
                new_height = int(template_img.height * scale_factor)
                scaled_template = template_img.resize(
                    (new_width, new_height), Image.LANCZOS
                )

                # 缓存PIL图像对象
                self.template_cache[filename] = scaled_template
            except Exception as e:
                logging.warning(f"加载或缩放模板出错: {filename}, {e}")
                continue
            loaded_count += 1
            # logging.debug(f"已缓存模板: {filename} ({new_size[0]}x{new_size[1]})")

        logging.info(f"模板加载完成，共加载 {loaded_count} 个模板")

    def _init_window_capturer(self):
        """初始化崩坏3游戏窗口捕获器（延迟加载）"""
        if self.window_capturer is None:
            logging.info("初始化窗口捕获器")
            self.window_capturer = WindowCapture(GAME_WINDOW_TITLE)
        return self.window_capturer

    def capture_screen(self):
        """捕获整个崩坏3游戏窗口的灰度图像（窗口检测优化）"""
        if not is_game_window_exist():
            return None
        capturer = self._init_window_capturer()
        pil_img = capturer.capture_window()
        if pil_img is None:
            logging.warning("屏幕捕获失败")
            return None
        return pil_img.convert("L")

    def match_template(self, template_name, screen_gray, threshold=0.8):
        """在屏幕图像中匹配指定模板，返回匹配位置和置信度"""
        # logging.debug(f"开始模板匹配: {template_name}")
        if template_name not in self.template_cache:
            logging.warning(f"模板不存在: {template_name}")
            return None, 0

        template = self.template_cache[template_name]
        if screen_gray is None:
            return None, 0

        # 将PIL图像转为numpy数组进行模板匹配
        screen_np = (
            np.array(screen_gray)
            if not isinstance(screen_gray, np.ndarray)
            else screen_gray
        )
        template_np = (
            np.array(template) if not isinstance(template, np.ndarray) else template
        )

        result = matchTemplate(screen_np, template_np, TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = minMaxLoc(result)
        # print(f"[DEBUG] 模板匹配结果 - 最大置信度: {max_val:.2f}")

        if max_val >= threshold:
            # 使用PIL图像的size属性替代numpy的shape
            template_width, template_height = template.size
            x = max_loc[0] + template_width // 2
            y = max_loc[1] + template_height // 2
            # print(f"[DEBUG] 找到匹配位置: ({x}, {y})")
            return (x, y), max_val
        return None, max_val

    def match_and_click(self, threshold=0.8):
        """匹配所有模板并点击置信度最高的位置（若激活游戏窗口成功）"""
        best_match = None
        best_confidence = 0
        screen_gray = self.capture_screen()

        for template_name in self.template_cache:
            location, confidence = self.match_template(
                template_name, screen_gray, threshold
            )
            if location and confidence > best_confidence:
                best_match = (template_name, location, confidence)
                best_confidence = confidence

        if best_match:
            template_name, (x, y), confidence = best_match
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))

            logging.info(
                f"匹配到位置: {template_name} @ ({x}, {y}), 置信度: {confidence:.2f}"
            )
            if active_game_window():
                pyautogui.click(x, y)
                logging.info("点击对应模板")
                return True
            else:
                logging.info("游戏窗口未激活，取消点击")
                return False
        return False

    @handle_exceptions("二维码解析出错", False)
    async def parse_qr_code(self, image_source="clipboard", config=None, bh_info=None):
        """从剪贴板或游戏窗口解析二维码并完成崩坏3登录"""
        if image_source == "clipboard":
            im = ImageGrab.grabclipboard()
            if not isinstance(im, Image.Image):
                return False
        elif image_source == "game_window":
            capturer = self._init_window_capturer()
            im = capturer.capture_window()
            if im is None:
                logging.warning("游戏窗口截图失败")
                return False
            im = im.convert("RGB")
        else:
            logging.warning("无效的图像来源")
            return False

        result = decode(im)
        if not result:
            return False

        url = result[0].data.decode("utf-8")

        if "ticket=" not in url:
            logging.debug("无效的二维码格式")
            return False

        ticket = next(
            (
                p.split("=")[1]
                for p in url.split("?")[1].split("&")
                if p.startswith("ticket=")
            ),
            None,
        )

        if ticket and config and bh_info:
            logging.info("检测到有效登陆票据，开始扫码验证")
            await mihoyosdk.scanCheck(bh_info, ticket, config)
            self.clear_clipboard()
            logging.info("扫码验证完成")
            return True

        logging.info("缺少必要的登陆信息")
        return False

    @handle_exceptions("清空剪贴板出错")
    def clear_clipboard(self):
        """清空系统剪贴板内容"""
        if windll.user32.OpenClipboard(None):
            windll.user32.EmptyClipboard()
            windll.user32.CloseClipboard()


# 初始化全局实例
image_processor = ImageProcessor()
