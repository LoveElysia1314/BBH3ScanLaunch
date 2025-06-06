# -*- coding: utf-8 -*-
"""
崩坏3自动登录图像处理模块 - 优化版
主要改进：
1. 改进模板缩放机制 - 基于文件名中的分辨率信息智能缩放
2. 优化屏幕捕获性能 - 使用更高效的截图方式
3. 增强匹配准确性 - 添加多尺度匹配和阈值控制
4. 改进游戏窗口区域获取逻辑
"""

import os
import time
import cv2
import numpy as np
import pyautogui
import pygetwindow as gw
from pyzbar.pyzbar import decode
from PIL import Image, ImageGrab
from ctypes import windll
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

class ImageProcessor:
    """图像处理引擎 - 优化版"""
    def __init__(self, template_dir=TEMPLATE_DIR):
        self.template_dir = template_dir
        self.screen_width, self.screen_height = pyautogui.size()
        self.template_cache = {}
        self._load_templates()
    
    def _get_resolution_from_filename(self, filename):
        """从文件名中提取分辨率信息"""
        match = re.search(r'(\d+)p', filename)
        return int(match.group(1)) if match else DEFAULT_RESOLUTION
    
    def _load_templates(self):
        """智能加载并缩放模板图片"""
        if not os.path.exists(self.template_dir):
            print(f"[INFO] 模板目录不存在: {self.template_dir}")
            return
        
        # 确保Default目录存在
        default_dir = os.path.join(self.template_dir, "Default")
        if not os.path.exists(default_dir):
            print(f"[INFO] 默认模板目录不存在: {default_dir}")
            return
        
        # 创建当前分辨率目录
        current_res_dir = os.path.join(self.template_dir, f"{self.screen_height}p")
        os.makedirs(current_res_dir, exist_ok=True)
        
        # 处理所有默认模板
        for filename in os.listdir(default_dir):
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
                
            src_path = os.path.join(default_dir, filename)
            dest_path = os.path.join(current_res_dir, filename)
            
            # 从文件名获取原始分辨率
            src_resolution = self._get_resolution_from_filename(filename)
            scale_factor = self.screen_height / src_resolution
            
            # 检查是否需要创建新模板
            if not os.path.exists(dest_path) or os.path.getmtime(src_path) > os.path.getmtime(dest_path):
                template = cv2.imread(src_path, cv2.IMREAD_GRAYSCALE)
                if template is None:
                    print(f"[INFO] 无法加载模板: {filename}")
                    continue
                    
                # 智能缩放
                new_width = int(template.shape[1] * scale_factor)
                new_height = int(template.shape[0] * scale_factor)
                template = cv2.resize(template, (new_width, new_height))
                cv2.imwrite(dest_path, template)
                print(f"[INFO] 创建缩放模板: {filename} ({new_width}x{new_height})")
            
            # 加载模板
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
        """高效屏幕捕获"""
        time.sleep(SCREENSHOT_DELAY)
        
        if region:
            left, top, width, height = region
            screenshot = pyautogui.screenshot(region=(left, top, width, height))
        else:
            screenshot = pyautogui.screenshot()
            
        screen_np = np.array(screenshot)
        return cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
    
    def match_template(self, template_name, threshold=0.8, region=None, scales=[1.0, 0.9, 1.1]):
        """
        多尺度模板匹配
        :param template_name: 模板文件名
        :param threshold: 匹配阈值
        :param region: 搜索区域
        :param scales: 缩放尺度列表
        :return: 匹配位置和置信度，或(None, 0)
        """
        if template_name not in self.template_cache:
            print(f"[INFO] 模板不存在: {template_name}")
            return None, 0
            
        template = self.template_cache[template_name]
        screen_gray = self.capture_screen(region)
        
        best_match_val = 0
        best_match_loc = None
        best_scale = 1.0
        
        # 多尺度匹配
        for scale in scales:
            scaled_template = cv2.resize(template, None, fx=scale, fy=scale)
            if scaled_template.shape[0] > screen_gray.shape[0] or scaled_template.shape[1] > screen_gray.shape[1]:
                continue
                
            result = cv2.matchTemplate(screen_gray, scaled_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val > best_match_val:
                best_match_val = max_val
                best_match_loc = max_loc
                best_scale = scale
        
        if best_match_val >= threshold:
            # 计算中心位置
            scaled_template = cv2.resize(template, None, fx=best_scale, fy=best_scale)
            x = best_match_loc[0] + scaled_template.shape[1] // 2
            y = best_match_loc[1] + scaled_template.shape[0] // 2
            
            if region:
                x += region[0]
                y += region[1]
                
            return (x, y), best_match_val
        
        return None, best_match_val
    
    def match_and_click(self, threshold=0.8, click_offset=(0, 0), region=None, max_attempts=1):
        """
        遍历当前分辨率对应模板目录下的所有图片，匹配到第一个符合要求的模板后点击并退出。
        
        :param threshold: 匹配阈值
        :param click_offset: 点击偏移量
        :param region: 搜索区域
        :param max_attempts: 每个模板的最大匹配尝试次数
        :return: 是否成功点击
        """
        print("[INFO] 开始尝试匹配当前分辨率下所有模板...")

        # 遍历所有缓存中的模板
        for template_name in self.template_cache:
            print(f"[INFO] 尝试匹配模板: {template_name}")
            for attempt in range(max_attempts):
                location, confidence = self.match_template(template_name, threshold, region)
                if location:
                    x, y = location
                    x += click_offset[0]
                    y += click_offset[1]

                    # 限制点击坐标在屏幕范围内
                    x = max(0, min(x, self.screen_width - 1))
                    y = max(0, min(y, self.screen_height - 1))

                    pyautogui.click(x, y)
                    print(f"[INFO] 成功匹配模板: {template_name} (置信度: {confidence:.2f}) @ ({x}, {y})")
                    return True
                print(f"[INFO] 模板 {template_name} 第 {attempt+1}/{max_attempts} 次匹配失败 (置信度: {confidence:.2f})")
                time.sleep(0.5)

        print("[INFO] 所有模板均未匹配成功")
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
                    
                left, top, width, height = region
                im = pyautogui.screenshot(region=(left, top, width, height))
            else:
                return False
            
            print("[INFO] 识别二维码...")
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
                await mihoyosdk.scanCheck(lambda msg: print(msg), bh_info, ticket, config)
                time.sleep(1)
                self.clear_clipboard()
                return True
            else:
                print("[INFO] 成功解析二维码，但缺少登录信息")
                return False
        except Exception as e:
            print(f"解析二维码失败: {str(e)}")
            return False
    
    def switch_to_qr_login_mode(self):
        """切换到扫码登录模式"""
        region = self.get_game_window_region()
        if not region:
            return False
        
        left, top, width, height = region
        switch_x = left + width * 0.7
        switch_y = top + height - 100
        
        try:
            pyautogui.press('esc')
            time.sleep(1)
            pyautogui.click(switch_x, switch_y)
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"切换登录模式失败: {str(e)}")
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