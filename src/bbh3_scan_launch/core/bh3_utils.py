# -*- coding: utf-8 -*-
import os
import re
import numpy as np
import logging
import psutil
import ctypes
from cv2 import matchTemplate, TM_CCOEFF_NORMED, minMaxLoc
from PIL import Image, ImageGrab
from pyzbar.pyzbar import decode
from urllib.parse import parse_qs, urlparse
from .sdk import mihoyosdk
from .game_window import GameWindowService
from ..constants import TEMPLATE_PICTURES_DIR
from ..utils.exception_utils import handle_exceptions
from ..utils.notification_service import NotificationSink, create_noop_sink

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

    def __init__(self, config_manager, game_window=None, notifier=None):
        self.game_path = None
        self._config_manager = config_manager
        self._game_window = game_window or GameWindowService(
            lambda: self._config_manager.get_config("game_path", "")
        )
        self._notifier = notifier or create_noop_sink()
        self._load_game_path()

    def _load_game_path(self):
        """加载游戏路径配置"""
        config = self._config_manager.config
        self.game_path = config.get("game_path")

    def set_notifier(self, notifier: NotificationSink):
        """
        注入通知器，默认行为为日志+静默兜底。
        """
        self._notifier = notifier or create_noop_sink()

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
        return start_bh3(self.game_path)

    def _show_message(self, show_messages, title, text, is_warning=False):
        """
        统一展示信息，默认走注入的 notifier。
        """
        if not show_messages:
            return
        if is_warning:
            self._notifier.warning(title, text)
        else:
            self._notifier.info(title, text)

    def is_game_window_exist(self):
        """检查崩坏3游戏窗口是否存在"""
        return self._game_window.exists()

    def launch_game(self, show_messages=True):
        """
        启动游戏
        """
        # 配置可能在运行时被用户改动，启动前重新读取一次
        self._load_game_path()
        if not self.game_path:
            msg = "请先配置游戏路径！"
            logging.info(msg)
            self._show_message(show_messages, "路径未配置", msg, is_warning=True)
            return False

        # 检查进程，防止重复启动
        if self.is_bh3_running():
            logging.info("崩坏3已在运行，无需重复启动")
            return False
        logging.info("正在启动崩坏3...")
        try:
            self.start_bh3()
            logging.info("崩坏3已启动")
            return True
        except Exception as e:
            logging.error(f"启动游戏失败: {e}")
            self._show_message(
                show_messages, "启动失败", f"无法启动游戏: {e}", is_warning=True
            )
            return False

    def one_click_login(self, skip_launch=False, show_messages=True):
        """
        一键登录模式，支持跳过游戏启动（防止重复打开游戏）
        :param skip_launch: 如果为 True，则不执行 launchGame
        :param show_messages: 是否显示消息框
        """
        # 如果不跳过启动，则调用统一的启动方法
        if not skip_launch:
            launch_result = self.launch_game(show_messages=show_messages)
            if not launch_result and not self.is_bh3_running():
                return False

        # 这里可以添加一键登录的逻辑，但由于依赖UI，可能需要外部处理
        logging.info("一键进入舰桥模式已启用")
        return True

    async def auto_monitor(
        self,
        config,
        image_processor,
        exit_app_func=None,
    ):
        """
        自动监控和处理游戏窗口
        :param config: 配置字典
        :param image_processor: ImageProcessor 实例
        :param exit_app_func: 退出应用的函数（可选）
        """
        import asyncio
        import ctypes

        bh_info = self._config_manager.bh_info

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
                        qr_parsed = await image_processor.parse_qr_code(
                            image_source="game_window",
                            config=config,
                            bh_info=bh_info,
                        )
                        if qr_parsed:
                            if config.get("auto_click"):
                                logging.info("扫码成功，4秒后将自动点击窗口中心")
                                await asyncio.sleep(4)
                                self._game_window.click_center()
                            if config.get("auto_close") and exit_app_func:
                                logging.info("已启用自动退出，2秒后将关闭扫码器")
                                await asyncio.sleep(2)
                                exit_app_func()
                                return

                # 处理剪贴板检查：无论是否开启自动截图，只要已登录就尝试从剪贴板识别二维码
                if config.get("account_login", False):
                    await image_processor.parse_qr_code(
                        image_source="clipboard",
                        config=config,
                        bh_info=bh_info,
                    )

                # 根据配置的间隔时间等待
                await asyncio.sleep(config.get("sleep_time", 1))

            except Exception as e:
                logging.error(f"自动监控过程中发生错误: {str(e)}")
                await asyncio.sleep(1)

    def _is_admin(self):
        """检查管理员权限"""
        return ctypes.windll.shell32.IsUserAnAdmin()


class ImageProcessor:
    """
    图像处理引擎
    提供模板匹配、屏幕捕获和二维码识别功能，用于崩坏3游戏界面识别
    """

    def __init__(self, template_dir=TEMPLATE_DIR, game_window=None):
        logging.info("初始化图像处理器")
        self.template_dir = template_dir
        self.game_window = game_window or GameWindowService()
        self.template_cache = {}
        self.template_resolutions = {}
        self._scaled_template_cache = {}
        self._load_templates()

    def _get_resolution_from_filename(self, filename):
        """从模板文件名中提取分辨率信息"""
        match = re.search(r"(\d+)p", filename)
        return int(match.group(1)) if match else None

    def _load_templates(self):
        """加载原始模板；匹配时再按游戏客户区高度缩放。"""
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
                with Image.open(file_path) as template_img:
                    self.template_cache[filename] = template_img.convert("L")
                self.template_resolutions[filename] = src_resolution
            except Exception as e:
                logging.warning(f"加载或缩放模板出错: {filename}, {e}")
                continue
            loaded_count += 1
            # logging.debug(f"已缓存模板: {filename} ({new_size[0]}x{new_size[1]})")

        logging.info(f"模板加载完成，共加载 {loaded_count} 个模板")

    def _get_scaled_template(self, template_name, target_height):
        cache_key = (template_name, target_height)
        if cache_key in self._scaled_template_cache:
            return self._scaled_template_cache[cache_key]

        source = self.template_cache[template_name]
        source_height = self.template_resolutions[template_name]
        scale_factor = target_height / source_height
        new_size = (
            max(1, round(source.width * scale_factor)),
            max(1, round(source.height * scale_factor)),
        )
        scaled = source.resize(new_size, Image.Resampling.LANCZOS)
        self._scaled_template_cache[cache_key] = scaled
        return scaled

    def capture_screen(self):
        """捕获已验证的游戏客户区灰度图像。"""
        pil_img = self.game_window.capture()
        if pil_img is None:
            logging.debug("游戏窗口捕获失败")
            return None
        return pil_img.convert("L")

    def match_template(self, template_name, screen_gray, threshold=0.8):
        """在屏幕图像中匹配指定模板，返回匹配位置和置信度"""
        # logging.debug(f"开始模板匹配: {template_name}")
        if template_name not in self.template_cache:
            logging.warning(f"模板不存在: {template_name}")
            return None, 0

        if screen_gray is None:
            return None, 0

        # 将PIL图像转为numpy数组进行模板匹配
        screen_np = (
            np.array(screen_gray)
            if not isinstance(screen_gray, np.ndarray)
            else screen_gray
        )
        screen_height, screen_width = screen_np.shape[:2]
        template = self._get_scaled_template(template_name, screen_height)
        template_np = (
            np.array(template) if not isinstance(template, np.ndarray) else template
        )
        if template_np.shape[0] > screen_height or template_np.shape[1] > screen_width:
            return None, 0

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
        if screen_gray is None:
            logging.debug("未能获取游戏窗口截图，终止匹配点击")
            return False

        for template_name in self.template_cache:
            location, confidence = self.match_template(
                template_name, screen_gray, threshold
            )
            if location and confidence > best_confidence:
                best_match = (template_name, location, confidence)
                best_confidence = confidence

        if best_match:
            template_name, (x, y), confidence = best_match

            logging.info(
                f"匹配到位置: {template_name} @ ({x}, {y}), 置信度: {confidence:.2f}"
            )
            if self.game_window.click_client(x, y):
                logging.info("点击对应模板")
                return True
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
            im = self.game_window.capture()
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

        ticket = parse_qs(urlparse(url).query).get("ticket", [None])[0]

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
        if ctypes.windll.user32.OpenClipboard(None):
            ctypes.windll.user32.EmptyClipboard()
            ctypes.windll.user32.CloseClipboard()
