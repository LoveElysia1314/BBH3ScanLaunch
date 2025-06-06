# -*- coding: utf-8 -*-
"""
崩坏3自动登录图像处理模块
功能特性：
1. 模板匹配引擎 - 用于识别游戏界面元素
2. 二维码解析引擎 - 用于识别登录二维码
3. 智能图像处理 - 优化资源使用
4. 异常安全处理
"""

import os
import time
import cv2
import numpy as np
import pyautogui
import pygetwindow as gw
from pyzbar.pyzbar import decode
from PIL import Image, ImageGrab
from functools import lru_cache
from ctypes import windll
import logging

# 配置 logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# 常量定义
TEMPLATE_DIR = "Pictures_to_Match"
SCREENSHOT_DELAY = 0.5  # 截图延迟时间(秒)
GAME_WINDOW_TITLE = "崩坏3"
TEMPLATE_SCALE_FACTOR = 8000  # 模板基准分辨率 (8000p)

def is_game_window_active():
    """
    检查当前活动窗口的标题是否与给定的 game_window_title 相匹配。
    
    :param game_window_title: 要检查的游戏窗口标题
    :return: 如果当前活动窗口的标题与 game_window_title 相匹配，返回 True；否则返回 False
    """
    try:
        active_window = gw.getActiveWindow()
        if active_window and active_window.title == GAME_WINDOW_TITLE:
            return True
        else:
            return False
    except Exception as e:
        print(f"检查活动窗口时出错: {e}")
        return False


class ImageProcessor:
    """图像处理引擎 - 整合模板匹配和二维码解析功能"""
    def __init__(self, template_dir=TEMPLATE_DIR):
        self.template_dir = template_dir
        self.screen_size = pyautogui.size()
        self.template_cache = {}
        self._load_templates()
    
    def _load_templates(self):
        """加载所有模板图片到缓存"""
        if not os.path.exists(self.template_dir):
            logger.warning("模板目录不存在 %s", self.template_dir)
            return
        
        for filename in os.listdir(self.template_dir):
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
                
            filepath = os.path.join(self.template_dir, filename)
            template = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
            if template is None:
                logger.warning("无法加载模板 %s", filename)
                continue
                
            scale_factor = self.screen_size.height / TEMPLATE_SCALE_FACTOR
            if scale_factor != 1.0:
                new_size = (int(template.shape[1] * scale_factor),
                            int(template.shape[0] * scale_factor))
                template = cv2.resize(template, new_size)
                
            self.template_cache[filename] = template
            logger.info("加载模板: %s (%dx%d)", filename, template.shape[1], template.shape[0])
    
    @lru_cache(maxsize=1)
    def get_game_window_region(self):
        """获取游戏窗口区域并缓存结果"""
        try:
            windows = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)
            if windows:
                window = windows[0]
                if not window.isMinimized:
                    return (window.left, window.top, window.right, window.bottom)
            return None
        except Exception:
            return None
    
    def capture_full_screen(self):
        """捕获全屏并转换为灰度图"""
        time.sleep(SCREENSHOT_DELAY)
        screenshot = pyautogui.screenshot()
        screen_np = np.array(screenshot)
        return cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
    
    def capture_game_window(self):
        """捕获游戏窗口区域"""
        region = self.get_game_window_region()
        if not region:
            return None
        
        left, top, right, bottom = region
        width, height = right - left, bottom - top
        
        if width <= 0 or height <= 0:
            return None
            
        time.sleep(SCREENSHOT_DELAY)
        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        screen_np = np.array(screenshot)
        return cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
    
    def match_and_click(self, threshold=0.8, click_offset=(0, 0), region=None):
        """
        执行模板匹配并点击
        :param threshold: 匹配阈值 (0-1)
        :param click_offset: 点击位置偏移 (x, y)
        :param region: 指定搜索区域 (left, top, width, height)
        :return: 是否找到并点击了匹配项
        """
        if region:
            left, top, width, height = region
            screen_gray = pyautogui.screenshot(region=(left, top, width, height))
            screen_gray = cv2.cvtColor(np.array(screen_gray), cv2.COLOR_RGB2GRAY)
            global_offset = (left, top)
        else:
            screen_gray = self.capture_full_screen()
            global_offset = (0, 0)
        
        for name, template in self.template_cache.items():
            result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                x_center = max_loc[0] + template.shape[1] // 2 + global_offset[0] + click_offset[0]
                y_center = max_loc[1] + template.shape[0] // 2 + global_offset[1] + click_offset[1]
                x_center = max(0, min(x_center, self.screen_size.width - 1))
                y_center = max(0, min(y_center, self.screen_size.height - 1))
                pyautogui.click(x_center, y_center)
                logger.info("点击匹配项: %s (置信度: %.2f @ (%d, %d))", name, max_val, x_center, y_center)
                return
        logger.debug("未找到匹配项")
        return

    async def parse_qr_code(self, image_source='clipboard', config=None, bh_info=None):
        """
        解析二维码并处理崩坏3登录
        :param image_source: 图片来源 'clipboard' 或 'game_window'
        :param config: 配置字典，用于登录验证
        :param bh_info: 崩坏3登录信息
        :return: 是否成功解析并完成登录
        """
        if image_source == 'clipboard':
            try:
                im = ImageGrab.grabclipboard()
                if not isinstance(im, Image.Image):
                    return
            except Exception as e:
                logger.error("获取剪贴板图像失败: %s", str(e))
                return
        elif image_source == 'game_window':
            region = self.get_game_window_region()
            if not region:
                return
                
            left, top, right, bottom = region
            width, height = right - left, bottom - top
            if width <= 0 or height <= 0:
                return
                
            im = pyautogui.screenshot(region=(left, top, width, height))
        else:
            return
        
        logger.info("识别二维码...")
        try:
            result = decode(im)
            if not result:
                logger.debug("未找到二维码")
                return
                
            url = result[0].data.decode('utf-8')
            if 'ticket=' not in url:
                logger.debug("无效的登录二维码")
                return
                
            params = url.split('?')[1].split('&')
            ticket = next((p.split('=')[1] for p in params if p.startswith('ticket=')), None)
            
            if ticket and config and bh_info:
                logger.info("二维码识别成功，开始请求崩坏3服务器完成扫码")
                import mihoyosdk
                await mihoyosdk.scanCheck(lambda msg: logger.info(msg), bh_info, ticket, config)
                time.sleep(1)
                self.clear_clipboard()
                return
            else:
                logger.debug("成功解析二维码，但缺少登录信息")
                return
        except Exception as e:
            logger.error("解析二维码失败: %s", str(e))
            return
    
    def switch_to_qr_login_mode(self):
        """切换到扫码登录模式"""
        region = self.get_game_window_region()
        if not region:
            return
        
        left, top, right, bottom = region
        window_width = right - left
        switch_x = left + window_width * 0.7
        switch_y = bottom - 100
        switch_x = max(left, min(switch_x, right - 1))
        switch_y = max(top, min(switch_y, bottom - 1))
        
        try:
            pyautogui.press('esc')
            time.sleep(1)
            pyautogui.click(switch_x, switch_y)
            time.sleep(0.5)
            return
        except Exception as e:
            logger.warning("切换登录模式失败: %s", str(e))
            return
    
    def clear_clipboard(self):
        """清空剪贴板"""
        try:
            if windll.user32.OpenClipboard(None):
                windll.user32.EmptyClipboard()
                windll.user32.CloseClipboard()
        except Exception as e:
            logger.error("清空剪贴板失败: %s", str(e))

image_processor = ImageProcessor()