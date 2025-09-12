# -*- coding: utf-8 -*-
import os
import re
import time
import numpy as np
import logging
from cv2 import matchTemplate, TM_CCOEFF_NORMED, minMaxLoc
from ctypes import windll
from PIL import Image, ImageGrab
import pyautogui
from pyzbar.pyzbar import decode
import win32con
import win32gui
import win32ui
import mihoyosdk

# 常量定义
TEMPLATE_DIR = "Pictures_to_Match"  # 模板图片目录
GAME_WINDOW_TITLE = "崩坏3"  # 游戏窗口标题


def is_game_window_exist():
    """检查崩坏3游戏窗口是否存在"""
    try:

        def enum_windows(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title == GAME_WINDOW_TITLE:
                    results.append(True)

        results = []
        win32gui.EnumWindows(enum_windows, results)
        exist = bool(results)
        logging.debug(f"游戏窗口存在检查: {'存在' if exist else '不存在'}")
        return exist
    except Exception as e:
        logging.error(f"检查窗口存在状态出错: {e}")
        return False


def active_game_window():
    """激活崩坏3游戏窗口并置于前台"""
    try:
        hwnd = win32gui.FindWindow(None, GAME_WINDOW_TITLE)
        if not hwnd:
            logging.debug("未找到游戏窗口")
            return False

        if win32gui.IsIconic(hwnd):
            logging.debug("恢复最小化窗口")
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.5)

        logging.debug("激活游戏窗口")
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        logging.error(f"激活窗口出错: {e}")
        return False


def click_center_of_game_window():
    """点击崩坏3游戏窗口中心位置"""
    if is_game_window_exist():
        hwnd = win32gui.FindWindow(None, GAME_WINDOW_TITLE)
        if not hwnd:
            logging.info("未找到游戏窗口")
            return

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top
        center_x = left + width // 2
        center_y = top + height // 2

        pyautogui.click(center_x, center_y)
        logging.debug(f"已点击窗口中心: ({center_x}, {center_y})")


class WindowCapture:
    """
    后台窗口截图工具类
    使用Windows API实现后台窗口截图功能，支持对崩坏3游戏窗口的截图
    """

    def __init__(self, window_title):
        logging.debug(f"初始化窗口捕获器: {window_title}")
        self.window_title = window_title
        self.hwnd = None
        self._retry_count = 0

    def _find_window(self):
        """查找崩坏3游戏窗口句柄"""
        self.hwnd = win32gui.FindWindow(None, self.window_title)
        if self.hwnd:
            logging.debug(f"找到窗口句柄: {self.hwnd}")
            return True
        logging.debug(f"未找到窗口: {self.window_title}")
        return False

    def capture_window(self):
        """截取整个游戏窗口画面（支持后台窗口）"""
        try:
            if not self.hwnd and not self._find_window():
                logging.debug("无法获取窗口句柄，截图失败")
                return None

            left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
            width, height = right - left, bot - top
            logging.debug(f"窗口尺寸: {width}x{height}")

            hwndDC = win32gui.GetWindowDC(self.hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

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

            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hwndDC)
            return pil_img
        except Exception as e:
            logging.error(f"窗口捕获出错: {e}")
            self.hwnd = None
            return None


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
        logging.debug("开始加载模板到内存")
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
        """捕获整个崩坏3游戏窗口的灰度图像"""
        # logging.debug("开始屏幕捕获")
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
        min_val, max_val, min_loc, max_loc = minMaxLoc(result)
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
        logging.debug("开始模板匹配点击流程")
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
        logging.debug("未找到符合条件的匹配")
        return False

    async def parse_qr_code(self, image_source="clipboard", config=None, bh_info=None):
        """从剪贴板或游戏窗口解析二维码并完成崩坏3登录"""
        try:
            if image_source == "clipboard":
                logging.debug("从剪贴板获取图像")
                im = ImageGrab.grabclipboard()
                if not isinstance(im, Image.Image):
                    return False
            elif image_source == "game_window":
                logging.debug("从游戏窗口获取图像")
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
                logging.debug("未检测到二维码")
                return False

            url = result[0].data.decode("utf-8")
            logging.debug(f"解码URL: {url}")

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

        except Exception as e:
            logging.error(f"二维码解析出错: {e}")
            return False

    def clear_clipboard(self):
        """清空系统剪贴板内容"""
        try:
            logging.debug("清空剪贴板")
            if windll.user32.OpenClipboard(None):
                windll.user32.EmptyClipboard()
                windll.user32.CloseClipboard()
                logging.debug("剪贴板已清空")
        except Exception as e:
            logging.error(f"清空剪贴板出错: {e}")


# 初始化全局实例
image_processor = ImageProcessor()
