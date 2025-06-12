# -*- coding: utf-8 -*-
import os
import re
import time
import cv2
import numpy as np
from ctypes import windll
from PIL import Image, ImageGrab
import pyautogui
from pyzbar.pyzbar import decode
import win32con
import win32gui
import win32ui
import mihoyosdk

# 常量定义
TEMPLATE_DIR = "Pictures_to_Match"
SCREENSHOT_DELAY = 0.2  # 截图延迟时间
GAME_WINDOW_TITLE = "崩坏3"

def is_game_window_exist():
    """检查所有窗口中是否存在标题全字匹配GAME_WINDOW_TITLE的窗口"""
    try:
        def enum_windows(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title == GAME_WINDOW_TITLE:
                    results.append(True)
        results = []
        win32gui.EnumWindows(enum_windows, results)
        exist = bool(results)
        print(f"[DEBUG] 游戏窗口存在检查: {'存在' if exist else '不存在'}")
        return exist
    except Exception as e:
        print(f"[ERROR] 检查窗口存在状态出错: {e}")
        return False

def active_game_window():
    """激活指定标题的游戏窗口"""
    try:
        hwnd = win32gui.FindWindow(None, GAME_WINDOW_TITLE)
        if not hwnd:
            print("[DEBUG] 未找到游戏窗口")
            return False
        
        if win32gui.IsIconic(hwnd):
            print("[DEBUG] 恢复最小化窗口")
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.5)
        
        print("[DEBUG] 激活游戏窗口")
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        print(f"[ERROR] 激活窗口出错: {e}")
        return False

def click_center_of_game_window():
    """
    激活GAME_WINDOW_TITLE对应窗口并点击中心位置。
    """
    if is_game_window_exist():
        hwnd = win32gui.FindWindow(None, GAME_WINDOW_TITLE)
        if not hwnd:
            print("[INFO] 未找到游戏窗口")
            return
        
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top
        center_x = left + width // 2
        center_y = top + height // 2
        
        pyautogui.click(center_x, center_y)
        print(f"[DEBUG]已点击窗口中心: ({center_x}, {center_y})")

class WindowCapture:
    """Windows 窗口截图工具类（支持后台窗口截图）"""
    def __init__(self, window_title):
        print(f"[DEBUG] 初始化窗口捕获器: {window_title}")
        self.window_title = window_title
        self.hwnd = None
        self._retry_count = 0

    def _find_window(self):
        """查找窗口句柄"""
        self.hwnd = win32gui.FindWindow(None, self.window_title)
        if self.hwnd:
            print(f"[DEBUG] 找到窗口句柄: {self.hwnd}")
            return True
        print(f"[DEBUG] 未找到窗口: {self.window_title}")
        return False

    def capture_window(self):
        """截取整个窗口画面（后台窗口）"""
        try:
            if not self.hwnd and not self._find_window():
                print("[DEBUG] 无法获取窗口句柄，截图失败")
                return None
            
            left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
            width, height = right - left, bot - top
            print(f"[DEBUG] 窗口尺寸: {width}x{height}")
            
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
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )
            
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hwndDC)
            return pil_img
        except Exception as e:
            print(f"[ERROR] 窗口捕获出错: {e}")
            self.hwnd = None
            return None

class ImageProcessor:
    """图像处理引擎 - 内存优化版"""
    def __init__(self, template_dir=TEMPLATE_DIR):
        print("[INFO] 初始化图像处理器")
        self.template_dir = template_dir
        self.screen_width, self.screen_height = self._get_screen_resolution()
        print(f"[INFO] 屏幕分辨率: {self.screen_width}x{self.screen_height}")
        self.template_cache = {}  # 内存缓存模板
        self.window_capturer = None  # 延迟初始化窗口捕获器
        self._load_templates()

    def _get_screen_resolution(self):
        """获取当前屏幕分辨率"""
        return windll.user32.GetSystemMetrics(0), windll.user32.GetSystemMetrics(1)

    def _get_resolution_from_filename(self, filename):
        """从文件名中提取分辨率信息（如 4000p）"""
        match = re.search(r'(\d+)p', filename)
        return int(match.group(1)) if match else None

    def _load_templates(self):
        """智能加载并缩放模板图片到内存"""
        print("[DEBUG] 开始加载模板到内存")
        if not os.path.exists(self.template_dir):
            os.makedirs(self.template_dir, exist_ok=True)
            print(f"[INFO] 已创建模板目录: {self.template_dir}")
            return

        loaded_count = 0
        for filename in os.listdir(self.template_dir):
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue

            file_path = os.path.join(self.template_dir, filename)
            src_resolution = self._get_resolution_from_filename(filename)
            
            if not src_resolution:
                print(f"[WARNING] 跳过文件（缺少有效分辨率标识）: {filename}")
                continue

            print(f"[DEBUG] 加载模板: {filename} (源分辨率: {src_resolution}p)")
            template = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                print(f"[WARNING] 无法加载模板: {filename}")
                continue

            # 计算缩放比例并缩放模板
            scale_factor = self.screen_height / src_resolution
            new_size = (int(template.shape[1] * scale_factor), 
                      int(template.shape[0] * scale_factor))
            scaled_template = cv2.resize(template, new_size)
            
            # 缓存缩放后的模板
            self.template_cache[filename] = scaled_template
            loaded_count += 1
            print(f"[DEBUG] 已缓存模板: {filename} ({new_size[0]}x{new_size[1]})")

        print(f"[INFO] 模板加载完成，共加载 {loaded_count} 个模板")

    def _init_window_capturer(self):
        """初始化窗口捕获器（延迟初始化）"""
        if self.window_capturer is None:
            print("[INFO] 初始化窗口捕获器")
            self.window_capturer = WindowCapture(GAME_WINDOW_TITLE)
        return self.window_capturer

    def capture_screen(self):
        """高效屏幕捕获（整个游戏窗口）"""
        print("[DEBUG] 开始屏幕捕获")
        capturer = self._init_window_capturer()
        pil_img = capturer.capture_window()
        if pil_img is None:
            print("[WARNING] 屏幕捕获失败")
            return None
        
        screen_np = np.array(pil_img)
        return cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)

    def match_template(self, template_name, screen_gray, threshold=0.8):
        """
        单尺度模板匹配
        :param template_name: 模板文件名
        :param threshold: 匹配阈值
        :return: 匹配位置和置信度，或(None, 0)
        """
        #print(f"[DEBUG] 开始模板匹配: {template_name}")
        if template_name not in self.template_cache:
            print(f"[WARNING] 模板不存在: {template_name}")
            return None, 0

        template = self.template_cache[template_name]
        if screen_gray is None:
            return None, 0

        result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        #print(f"[DEBUG] 模板匹配结果 - 最大置信度: {max_val:.2f}")
        
        if max_val >= threshold:
            x = max_loc[0] + template.shape[1] // 2
            y = max_loc[1] + template.shape[0] // 2
            #print(f"[DEBUG] 找到匹配位置: ({x}, {y})")
            return (x, y), max_val
        return None, max_val

    def match_and_click(self, threshold=0.8):
        """
        遍历模板目录下的所有图片，点击置信度最高的匹配结果
        :return: 是否成功点击
        """
        print("[DEBUG] 开始模板匹配点击流程")
        best_match = None
        best_confidence = 0
        screen_gray = self.capture_screen()
        
        for template_name in self.template_cache:
            location, confidence = self.match_template(template_name, screen_gray, threshold)
            if location and confidence > best_confidence:
                best_match = (template_name, location, confidence)
                best_confidence = confidence

        if best_match:
            template_name, (x, y), confidence = best_match
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))
            
            print(f"[INFO] 匹配到位置: {template_name} @ ({x}, {y}), 置信度: {confidence:.2f}")
            if active_game_window():
                pyautogui.click(x, y)
                print(f"[INFO] 点击对应模板")
                return True
            else:
                print(f"[INFO] 游戏窗口未激活，取消点击")
                return False
        print("[DEBUG] 未找到符合条件的匹配")
        return False

    async def parse_qr_code(self, image_source="clipboard", config=None, bh_info=None):
        """
        解析二维码并处理崩坏3登陆
        :param image_source: 图片来源 'clipboard' 或 'game_window'
        :return: 是否成功解析
        """
        try:
            if image_source == 'clipboard':
                print("[DEBUG] 从剪贴板获取图像")
                im = ImageGrab.grabclipboard()
                if not isinstance(im, Image.Image):
                    return False
            elif image_source == 'game_window':
                print("[DEBUG] 从游戏窗口获取图像")
                capturer = self._init_window_capturer()
                im = capturer.capture_window()
                if im is None:
                    print("[WARNING] 游戏窗口截图失败")
                    return False
                im = im.convert('RGB')
            else:
                print("[WARNING] 无效的图像来源")
                return False

            result = decode(im)
            if not result:
                print("[DEBUG] 未检测到二维码")
                return False
            
            url = result[0].data.decode('utf-8')
            print(f"[DEBUG] 解码URL: {url}")
            
            if 'ticket=' not in url:
                print("[DEBUG] 无效的二维码格式")
                return False
                
            ticket = next((p.split('=')[1] for p in url.split('?')[1].split('&') 
                          if p.startswith('ticket=')), None)
                          
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
            print("[DEBUG] 清空剪贴板")
            if windll.user32.OpenClipboard(None):
                windll.user32.EmptyClipboard()
                windll.user32.CloseClipboard()
                print("[DEBUG] 剪贴板已清空")
        except Exception as e:
            print(f"[ERROR] 清空剪贴板出错: {e}")

# 初始化全局实例
image_processor = ImageProcessor()