# -*- coding: utf-8 -*-
import asyncio
import os
import re
import time
import cv2
import numpy as np
from ctypes import windll
from PIL import Image, ImageGrab
import pyautogui
import pygetwindow as gw
from pyzbar.pyzbar import decode
from screeninfo import get_monitors
import win32con
import win32gui
import win32ui
import mihoyosdk

TEMPLATE_DIR = "Pictures_to_Match"
SCREENSHOT_DELAY = 0.2
GAME_WINDOW_TITLE = "崩坏3"
DEFAULT_RESOLUTION = 8000

def get_game_window():
    """获取游戏窗口对象"""
    try:
        windows = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)
        return windows[0] if windows else None
    except Exception as e:
        print(f"[ERROR] 窗口操作出错: {e}")
        return None

def click_center_of_game_window():
    """点击游戏窗口中心"""
    if window := get_game_window():
        center_x = window.left + window.width // 2
        center_y = window.top + window.height // 2
        pyautogui.click(center_x, center_y)
        print(f"[DEBUG] 已点击窗口中心: ({center_x}, {center_y})")

def is_game_window_exist():
    """检查游戏窗口是否存在"""
    return bool(get_game_window())

def active_game_window():
    """激活游戏窗口"""
    if window := get_game_window():
        if window.isMinimized:
            window.restore()
            time.sleep(0.5)
        window.activate()
        return True
    return False

class WindowCapture:
    """Windows窗口截图工具类"""
    
    def __init__(self, window_title):
        self.window_title = window_title
        self.hwnd = None

    def _find_window(self):
        self.hwnd = win32gui.FindWindow(None, self.window_title)
        return bool(self.hwnd)

    def capture_window(self):
        """截取整个窗口画面"""
        if not self.hwnd and not self._find_window():
            return None
            
        try:
            left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
            w, h = right - left, bot - top
            
            with win32gui.GetWindowDC(self.hwnd) as hwndDC, \
                 win32ui.CreateDCFromHandle(hwndDC) as mfcDC, \
                 mfcDC.CreateCompatibleDC() as saveDC:
                
                saveBitMap = win32ui.CreateBitmap()
                saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
                saveDC.SelectObject(saveBitMap)
                
                if not windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 0):
                    saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY)
                
                bmpinfo = saveBitMap.GetInfo()
                bmpstr = saveBitMap.GetBitmapBits(True)
                return Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), 
                                        bmpstr, 'raw', 'BGRX', 0, 1)
        except Exception as e:
            print(f"[ERROR] 窗口捕获出错: {e}")
            self.hwnd = None
            return None

class ImageProcessor:
    """图像处理引擎优化版"""
    
    def __init__(self, template_dir=TEMPLATE_DIR):
        self.template_dir = template_dir
        self.screen_width, self.screen_height = get_monitors()[0].width, get_monitors()[0].height
        self.template_cache = {}
        self.window_capturer = None
        self._load_templates()

    def _get_resolution(self, filename):
        match = re.search(r'(\d+)p', filename)
        return int(match.group(1)) if match else DEFAULT_RESOLUTION

    def create_scaled_template(self, src_path, dest_path, scale_factor):
        """创建缩放后的模板"""
        template = cv2.imread(src_path, cv2.IMREAD_GRAYSCALE)
        if template is None: 
            print(f"[WARNING] 无法读取模板: {src_path}")
            return None
        
        new_size = (int(template.shape[1] * scale_factor), 
                    int(template.shape[0] * scale_factor))
        template = cv2.resize(template, new_size)
        cv2.imwrite(dest_path, template)
        return template

    def _load_templates(self):
        """智能加载并缩放模板图片"""
        default_dir = os.path.join(self.template_dir, "Default")
        if not os.path.exists(default_dir):
            print(f"[WARNING] 默认模板目录不存在: {default_dir}")
            return

        current_res_dir = os.path.join(self.template_dir, f"{self.screen_height}p")
        os.makedirs(current_res_dir, exist_ok=True)
        
        for filename in os.listdir(default_dir):
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
            
            src_path = os.path.join(default_dir, filename)
            dest_path = os.path.join(current_res_dir, filename)
            scale_factor = self.screen_height / self._get_resolution(filename)
            
            # 创建或更新缩放模板
            if not os.path.exists(dest_path) or os.path.getmtime(src_path) > os.path.getmtime(dest_path):
                self.create_scaled_template(src_path, dest_path, scale_factor)
                
            # 加载模板到缓存 - 修复了这里的问题
            template = cv2.imread(dest_path, cv2.IMREAD_GRAYSCALE)
            if template is not None:  # 检查是否成功读取图像
                self.template_cache[filename] = template
                print(f"[DEBUG] 加载模板: {filename} ({template.shape[1]}x{template.shape[0]})")

    def capture_screen(self):
        """高效屏幕捕获"""
        if self.window_capturer is None:
            self.window_capturer = WindowCapture(GAME_WINDOW_TITLE)
            
        if pil_img := self.window_capturer.capture_window():
            return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
        return None

    def match_template(self, template_name, threshold=0.8):
        """单尺度模板匹配"""
        if template_name not in self.template_cache:
            print(f"[WARNING] 模板不存在: {template_name}")
            return None, 0
            
        screen_gray = self.capture_screen()
        if screen_gray is None: 
            print("[WARNING] 屏幕捕获失败")
            return None, 0
        
        result = cv2.matchTemplate(screen_gray, self.template_cache[template_name], cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= threshold:
            x = max_loc[0] + self.template_cache[template_name].shape[1] // 2
            y = max_loc[1] + self.template_cache[template_name].shape[0] // 2
            return (x, y), max_val
        return None, max_val

    def match_and_click(self, threshold=0.8):
        """遍历模板并点击最佳匹配"""
        best_match = (None, 0)
        screen_gray = self.capture_screen()
        if screen_gray is None:
            print("[DEBUG] 无法捕获屏幕，因此无法匹配模板")
            return False
        
        for template_name, template in self.template_cache.items():
            result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            if max_val > best_match[1] and max_val >= threshold:
                x = max_loc[0] + template.shape[1] // 2
                y = max_loc[1] + template.shape[0] // 2
                best_match = ((x, y), max_val)
        
        if best_match[0]:
            x, y = best_match[0]
            active_game_window()
            time.sleep(0.5)
            pyautogui.click(x, y)
            print(f"[INFO] 点击匹配位置: ({x}, {y}), 置信度: {best_match[1]:.2f}")
            return True
        print("[DEBUG] 未找到符合条件的匹配")
        return False

    def get_image_from_source(self, image_source):
        """统一获取图像来源"""
        if image_source == 'clipboard':
            return ImageGrab.grabclipboard()
        elif image_source == 'game_window':
            if self.window_capturer is None:
                self.window_capturer = WindowCapture(GAME_WINDOW_TITLE)
            return self.window_capturer.capture_window()
        return None

    async def parse_qr_code(self, image_source="clipboard", config=None, bh_info=None):
        """解析二维码并处理登录"""
        if not (im := self.get_image_from_source(image_source)):
            print(f"[DEBUG] 无法从 {image_source} 获取图像")
            return False
        
        try:
            result = decode(im)
            if not result:
                print("[DEBUG] 未检测到二维码")
                return False
                
            url = result[0].data.decode('utf-8')
            print(f"[DEBUG] 解码URL: {url}")
            
            if 'ticket=' not in url:
                print("[DEBUG] 无效的二维码格式")
                return False
                
            # 提取ticket参数
            params = url.split('?')[1].split('&')
            ticket = next((p.split('=')[1] for p in params if p.startswith('ticket=')))
            
            if ticket and config and bh_info:
                print("[INFO] 检测到有效登陆票据")
                print("[INFO] 开始扫码验证")
                await mihoyosdk.scanCheck(bh_info, ticket, config)
                self.clear_clipboard()
                print("[INFO] 扫码验证完成")
                return True
                
            print("[INFO] 缺少必要的登陆信息")
            return False
        except Exception as e:
            print(f"[ERROR] 二维码解析出错: {e}")
            return False

    def clear_clipboard(self):
        """清空剪贴板"""
        try:
            if windll.user32.OpenClipboard(None):
                windll.user32.EmptyClipboard()
                windll.user32.CloseClipboard()
        except Exception as e:
            print(f"[ERROR] 清空剪贴板出错: {e}")

image_processor = ImageProcessor()