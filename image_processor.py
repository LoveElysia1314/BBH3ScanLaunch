# -*- coding: utf-8 -*-
"""
崩坏3自动登录图像处理模块 - 重构版（后台窗口截图支持）
主要改进：
1. 使用 PrintWindow 截图技术实现后台窗口捕获
2. 封装窗口管理器，提高代码复用率
3. 保留模板缩放机制和二维码识别等功能
"""

import os
import time
import cv2
import numpy as np
import pygetwindow as gw
from pyzbar.pyzbar import decode
from PIL import Image ,ImageGrab
from ctypes import windll, c_int, WinDLL
import re

# 常量定义
TEMPLATE_DIR = "Pictures_to_Match"
SCREENSHOT_DELAY = 0.2  # 缩短截图延迟时间
GAME_WINDOW_TITLE = "崩坏3"
DEFAULT_RESOLUTION = 8000  # 默认模板分辨率


def is_game_window_active():
    """检查崩坏3窗口是否激活"""
    try:
        active_window = gw.getActiveWindow()
        return GAME_WINDOW_TITLE == active_window.title
    except Exception as e:
        print(f"[INFO] 检查活动窗口时出错: {e}")
        return False


def is_game_window_exist():
    """检查所有窗口中是否存在标题全字匹配GAME_WINDOW_TITLE的窗口"""
    try:
        all_windows = gw.getAllWindows()
        for window in all_windows:
            if window.title == GAME_WINDOW_TITLE:
                return True
        return False
    except Exception as e:
        print(f"[INFO] 检查窗口时出错: {e}")
        return False


def active_game_window():
    """
    激活指定标题的游戏窗口（如“崩坏3”）。
    若窗口存在，则将其置顶并恢复（如果最小化），否则不执行任何操作。

    :return: 是否成功激活窗口
    """
    try:
        # 查找所有标题匹配的窗口
        windows = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)

        if not windows:
            print(f"[INFO] 未找到标题为 '{GAME_WINDOW_TITLE}' 的窗口")
            return False

        window = windows[0]  # 取第一个匹配的窗口

        if window.isMinimized:
            window.restore()  # 如果窗口最小化，先恢复
            time.sleep(0.5)   # 等待恢复完成

        window.activate()     # 激活窗口（置顶并获得焦点）
        print(f"[INFO] 已成功激活窗口: {GAME_WINDOW_TITLE}")
        return True

    except Exception as e:
        print(f"[ERROR] 激活窗口失败: {e}")
        return False


class WindowCapture:
    """
    Windows 窗口截图工具类
    支持后台窗口截图（使用 PrintWindow API）
    """

    def __init__(self, window_title):
        self.window_title = window_title
        self.hwnd = None
        self._find_window()

    def _find_window(self):
        """查找窗口句柄"""
        self.hwnd = win32gui.FindWindow(None, self.window_title)
        if not self.hwnd:
            raise RuntimeError(f"未找到窗口: {self.window_title}")

    def capture_window(self, region=None):
        """截取窗口画面（即使在后台）"""
        left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
        width = right - left
        height = bot - top

        hwndDC = win32gui.GetWindowDC(self.hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()

        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(saveBitMap)

        result = windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 0)

        # 转换为 PIL 图像
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        pil_img = Image.frombuffer(
            'RGB',
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
            bmpstr, 'raw', 'BGRX', 0, 1
        )

        # 清理资源
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, hwndDC)

        # 区域裁剪
        if region:
            x, y, w, h = region
            pil_img = pil_img.crop((x, y, x + w, y + h))

        return pil_img


# 导入 win32 相关模块（放在后面避免导入顺序问题）
import win32gui
import win32ui
import win32con


class ImageProcessor:
    """图像处理引擎 - 重构版（支持后台窗口截图）"""

    def __init__(self, template_dir=TEMPLATE_DIR):
        self.template_dir = template_dir
        self.screen_width, self.screen_height = self._get_screen_resolution()
        self.template_cache = {}
        self.window_capturer = WindowCapture(GAME_WINDOW_TITLE)
        self._load_templates()

    def _get_screen_resolution(self):
        """获取当前屏幕分辨率"""
        from screeninfo import get_monitors
        monitor = get_monitors()[0]
        return monitor.width, monitor.height

    def _get_resolution_from_filename(self, filename):
        """从文件名中提取分辨率信息"""
        match = re.search(r'(\d+)p', filename)
        return int(match.group(1)) if match else DEFAULT_RESOLUTION

    def _load_templates(self):
        """智能加载并缩放模板图片"""
        if not os.path.exists(self.template_dir):
            print(f"[INFO] 模板目录不存在: {self.template_dir}")
            return

        default_dir = os.path.join(self.template_dir, "Default")
        if not os.path.exists(default_dir):
            print(f"[INFO] 默认模板目录不存在: {default_dir}")
            return

        current_res_dir = os.path.join(self.template_dir, f"{self.screen_height}p")
        os.makedirs(current_res_dir, exist_ok=True)

        for filename in os.listdir(default_dir):
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue

            src_path = os.path.join(default_dir, filename)
            dest_path = os.path.join(current_res_dir, filename)

            src_resolution = self._get_resolution_from_filename(filename)
            scale_factor = self.screen_height / src_resolution

            if not os.path.exists(dest_path) or os.path.getmtime(src_path) > os.path.getmtime(dest_path):
                template = cv2.imread(src_path, cv2.IMREAD_GRAYSCALE)
                if template is None:
                    print(f"[INFO] 无法加载模板: {filename}")
                    continue

                new_width = int(template.shape[1] * scale_factor)
                new_height = int(template.shape[0] * scale_factor)
                template = cv2.resize(template, (new_width, new_height))
                cv2.imwrite(dest_path, template)
                print(f"[INFO] 创建缩放模板: {filename} ({new_width}x{new_height})")

            template = cv2.imread(dest_path, cv2.IMREAD_GRAYSCALE)
            if template is not None:
                self.template_cache[filename] = template
                print(f"[DEBUG] 加载模板: {filename} ({template.shape[1]}x{template.shape[0]})")

    def get_game_window_region(self):
        """精确获取游戏窗口区域"""
        try:
            windows = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)
            if not windows:
                return None

            window = windows[0]
            if window.isMinimized:
                window.restore()
                time.sleep(0.5)

            return (window.left, window.top, window.width, window.height)
        except Exception as e:
            print(f"[INFO] 获取窗口区域失败: {e}")
            return None

    def capture_screen(self, region=None):
        """高效屏幕捕获（使用后台窗口截图）"""
        pil_img = self.window_capturer.capture_window(region)
        screen_np = np.array(pil_img)
        return cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)

    def match_template(self, template_name, threshold=0.8, region=None):
        """
        单尺度模板匹配
        :param template_name: 模板文件名
        :param threshold: 匹配阈值
        :param region: 搜索区域
        :return: 匹配位置和置信度，或(None, 0)
        """
        if template_name not in self.template_cache:
            print(f"[INFO] 模板不存在: {template_name}")
            return None, 0

        template = self.template_cache[template_name]
        screen_gray = self.capture_screen(region)

        result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            x = max_loc[0] + template.shape[1] // 2
            y = max_loc[1] + template.shape[0] // 2

            if region:
                x += region[0]
                y += region[1]

            return (x, y), max_val

        return None, max_val

    def match_and_click(self, threshold=0.8, region=None):
        """
        遍历模板目录下的所有图片，点击置信度最高的匹配结果

        :param threshold: 匹配阈值
        :param region: 搜索区域
        :return: 是否成功点击
        """
        best_match = None
        best_confidence = 0

        for template_name in self.template_cache:
            location, confidence = self.match_template(template_name, threshold, region)
            if location and confidence > best_confidence:
                best_match = (template_name, location, confidence)
                best_confidence = confidence

        if best_match:
            template_name, (x, y), confidence = best_match
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))

            import pyautogui
            pyautogui.click(x, y)
            print(f"[INFO] 点击最佳匹配: {template_name} (置信度: {confidence:.2f}) @ ({x}, {y})")
            return True

        print("[INFO] 未找到达到阈值的匹配结果")
        return False

    async def parse_qr_code(self, image_source='clipboard', config=None, bh_info=None):
        """
        解析二维码并处理崩坏3登录
        :param image_source: 图片来源 'clipboard' 或 'game_window'
        :param config: 配置字典
        :param bh_info: 崩坏3登录信息
        :return: 是否成功解析
        """
        try:
            if image_source == 'clipboard':
                im = ImageGrab.grabclipboard()
                if not isinstance(im, Image.Image):
                    print("[INFO] 剪贴板中没有图像")
                    return False
            elif image_source == 'game_window':
                region = self.get_game_window_region()
                if not region:
                    return False

                pil_im = self.window_capturer.capture_window(region)
                im = pil_im.convert('RGB')  # 确保是 RGB 格式
            else:
                return False

            result = decode(im)
            if not result:
                print("[INFO] 未找到二维码")
                return False

            url = result[0].data.decode('utf-8')
            if 'ticket=' not in url:
                print("[INFO] 无效的登录二维码")
                return False

            params = url.split('?')[1].split('&')
            ticket = next((p.split('=')[1] for p in params if p.startswith('ticket=')), None)

            if ticket and config and bh_info:
                print("[INFO] 二维码识别成功，开始请求崩坏3服务器完成扫码")
                import mihoyosdk
                await mihoyosdk.scanCheck(bh_info, ticket, config)
                time.sleep(1)
                self.clear_clipboard()
                return True
            else:
                print("[INFO] 成功解析二维码，但缺少登录信息")
                return False
        except Exception as e:
            print(f"解析二维码失败: {str(e)}")
            return False

    def clear_clipboard(self):
        """清空剪贴板"""
        try:
            if windll.user32.OpenClipboard(None):
                windll.user32.EmptyClipboard()
                windll.user32.CloseClipboard()
                print("[INFO] 剪贴板已清空")
        except Exception as e:
            print(f"清空剪贴板失败: {str(e)}")


image_processor = ImageProcessor()