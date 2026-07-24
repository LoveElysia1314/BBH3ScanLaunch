# -*- coding: utf-8 -*-
"""Windows 游戏窗口的发现、捕获和坐标操作。"""

from __future__ import annotations

import logging
import os
import time
from ctypes import c_void_p, windll
from dataclasses import dataclass
from typing import Callable

import psutil
import pyautogui
import win32api
import win32con
import win32gui
import win32process
import win32ui
from PIL import Image, ImageGrab

from ..constants import GAME_WINDOW_TITLE


def enable_per_monitor_dpi_awareness() -> bool:
    """在创建任何窗口前启用 Per-Monitor DPI V2，避免跨屏坐标虚拟化。"""
    try:
        if windll.user32.SetProcessDpiAwarenessContext(c_void_p(-4)):
            return True
    except (AttributeError, OSError):
        pass
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE
        return windll.shcore.SetProcessDpiAwareness(2) in (0, 0x80070005)
    except (AttributeError, OSError):
        logging.debug("无法显式启用按显示器 DPI 感知", exc_info=True)
        return False


@dataclass(frozen=True)
class GameWindow:
    """已经过进程身份验证的游戏顶层窗口。"""

    hwnd: int
    pid: int
    process_path: str
    title: str
    client_rect: tuple[int, int, int, int]

    @property
    def client_size(self) -> tuple[int, int]:
        left, top, right, bottom = self.client_rect
        return right - left, bottom - top


class GameWindowService:
    """定位 BH3.exe 窗口，并统一提供截图、激活及客户区坐标操作。"""

    def __init__(
        self,
        game_path_provider: Callable[[], str] | None = None,
        *,
        expected_process_name: str = "BH3.exe",
        title_hint: str = GAME_WINDOW_TITLE,
    ):
        self._game_path_provider = game_path_provider or (lambda: "")
        self._expected_process_name = expected_process_name.casefold()
        self._title_hint = title_hint
        self._hwnd: int | None = None
        self._last_monitor: int | None = None

    @staticmethod
    def _normalize_path(path: str | None) -> str:
        if not path:
            return ""
        return os.path.normcase(os.path.abspath(os.path.expandvars(path)))

    def _configured_path(self) -> str:
        try:
            return self._normalize_path(self._game_path_provider())
        except Exception:
            logging.debug("读取游戏路径失败", exc_info=True)
            return ""

    def _get_process_identity(self, pid: int) -> tuple[str, str]:
        try:
            process = psutil.Process(pid)
            process_path = self._normalize_path(process.exe())
            process_name = (process.name() or os.path.basename(process_path)).casefold()
            return process_path, process_name
        except (psutil.Error, OSError):
            logging.debug("无法读取窗口进程信息: PID %s", pid, exc_info=True)
            return "", ""

    def _get_client_rect(self, hwnd: int) -> tuple[int, int, int, int] | None:
        try:
            client_left, client_top, client_right, client_bottom = (
                win32gui.GetClientRect(hwnd)
            )
            width = client_right - client_left
            height = client_bottom - client_top
            if width <= 0 or height <= 0:
                return None
            left, top = win32gui.ClientToScreen(hwnd, (client_left, client_top))
            return left, top, left + width, top + height
        except win32gui.error:
            return None

    def _describe_candidate(self, hwnd: int) -> GameWindow | None:
        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return None
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_path, process_name = self._get_process_identity(pid)
            configured_path = self._configured_path()

            if configured_path:
                if process_path != configured_path:
                    return None
            elif process_name != self._expected_process_name:
                return None

            client_rect = self._get_client_rect(hwnd)
            if client_rect is None:
                return None
            return GameWindow(
                hwnd=hwnd,
                pid=pid,
                process_path=process_path,
                title=win32gui.GetWindowText(hwnd),
                client_rect=client_rect,
            )
        except (win32gui.error, OSError):
            return None

    def _candidate_score(self, window: GameWindow) -> tuple[int, int, int]:
        title_score = 2 if window.title == self._title_hint else 0
        if not title_score and self._title_hint.casefold() in window.title.casefold():
            title_score = 1
        foreground_score = int(win32gui.GetForegroundWindow() == window.hwnd)
        width, height = window.client_size
        return title_score, foreground_score, width * height

    def find(self, *, refresh: bool = False) -> GameWindow | None:
        """返回经过进程路径或进程名验证的最佳游戏窗口。"""
        if self._hwnd and not refresh:
            cached = self._describe_candidate(self._hwnd)
            if cached is not None:
                return cached

        candidates: list[GameWindow] = []

        def collect(hwnd, _):
            candidate = self._describe_candidate(hwnd)
            if candidate is not None:
                candidates.append(candidate)

        win32gui.EnumWindows(collect, None)
        if not candidates:
            self._hwnd = None
            return None

        selected = max(candidates, key=self._candidate_score)
        self._hwnd = selected.hwnd
        logging.debug(
            "已定位游戏窗口: hwnd=%s pid=%s title=%r path=%s",
            selected.hwnd,
            selected.pid,
            selected.title,
            selected.process_path,
        )
        return selected

    def exists(self) -> bool:
        return self.find() is not None

    def activate(self) -> bool:
        window = self.find()
        if window is None:
            return False
        hwnd = window.hwnd
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)
            win32gui.SetForegroundWindow(hwnd)
            if win32gui.GetForegroundWindow() != hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOP,
                    0,
                    0,
                    0,
                    0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
                )
                win32gui.SetForegroundWindow(hwnd)
            return win32gui.GetForegroundWindow() == hwnd
        except win32gui.error:
            logging.debug("激活游戏窗口失败", exc_info=True)
            self._hwnd = None
            return False

    @staticmethod
    def _is_usable_frame(image: Image.Image | None) -> bool:
        if image is None:
            return False
        low, high = image.convert("L").getextrema()
        return high > 8 and high - low > 1

    def _capture_with_print_window(self, window: GameWindow) -> Image.Image | None:
        width, height = window.client_size
        hwnd_dc = mfc_dc = save_dc = bitmap = None
        try:
            hwnd_dc = win32gui.GetDC(window.hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)

            captured = windll.user32.PrintWindow(
                window.hwnd,
                save_dc.GetSafeHdc(),
                3,  # PW_CLIENTONLY | PW_RENDERFULLCONTENT
            )
            if not captured:
                logging.debug("PrintWindow 未能捕获游戏客户区")
                return None

            bitmap_data = bitmap.GetBitmapBits(True)
            return Image.frombuffer(
                "RGB",
                (width, height),
                bitmap_data,
                "raw",
                "BGRX",
                0,
                1,
            )
        except Exception:
            logging.exception("捕获游戏窗口失败")
            self._hwnd = None
            return None
        finally:
            if bitmap is not None:
                try:
                    win32gui.DeleteObject(bitmap.GetHandle())
                except Exception:
                    pass
            if save_dc is not None:
                try:
                    save_dc.DeleteDC()
                except Exception:
                    pass
            if mfc_dc is not None:
                try:
                    mfc_dc.DeleteDC()
                except Exception:
                    pass
            if hwnd_dc is not None:
                try:
                    win32gui.ReleaseDC(window.hwnd, hwnd_dc)
                except Exception:
                    pass

    def _capture_from_desktop(self, window: GameWindow) -> Image.Image | None:
        """从虚拟桌面截取客户区，支持副屏及负坐标。"""
        if win32gui.IsIconic(window.hwnd):
            return None
        try:
            image = ImageGrab.grab(
                bbox=window.client_rect,
                all_screens=True,
            )
            return image if image.size == window.client_size else None
        except Exception:
            logging.debug("虚拟桌面捕获游戏窗口失败", exc_info=True)
            return None

    def capture(self) -> Image.Image | None:
        """捕获游戏客户区；PrintWindow 空帧时回退到跨显示器桌面捕获。"""
        window = self.find()
        if window is None:
            return None

        monitor = win32api.MonitorFromWindow(window.hwnd, 2)
        monitor_changed = (
            self._last_monitor is not None and monitor != self._last_monitor
        )
        self._last_monitor = monitor
        if monitor_changed:
            desktop_image = self._capture_from_desktop(window)
            if self._is_usable_frame(desktop_image):
                logging.debug("检测到游戏窗口跨显示器移动，已刷新桌面捕获")
                return desktop_image

        image = self._capture_with_print_window(window)
        if self._is_usable_frame(image):
            return image

        desktop_image = self._capture_from_desktop(window)
        if self._is_usable_frame(desktop_image):
            logging.debug("PrintWindow 返回空帧，已使用虚拟桌面捕获")
            return desktop_image
        return image if self._is_usable_frame(image) else None

    def client_to_screen(self, x: int, y: int) -> tuple[int, int] | None:
        window = self.find()
        if window is None:
            return None
        try:
            return win32gui.ClientToScreen(window.hwnd, (int(x), int(y)))
        except win32gui.error:
            self._hwnd = None
            return None

    def click_client(self, x: int, y: int, *, activate: bool = True) -> bool:
        if activate and not self.activate():
            return False
        point = self.client_to_screen(x, y)
        if point is None:
            return False
        pyautogui.click(*point)
        return True

    def click_center(self) -> bool:
        window = self.find()
        if window is None:
            logging.info("未找到游戏窗口")
            return False
        width, height = window.client_size
        return self.click_client(width // 2, height // 2)
