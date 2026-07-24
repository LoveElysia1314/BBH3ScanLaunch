import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from bbh3_scan_launch.core.bh3_utils import ImageProcessor
from bbh3_scan_launch.core.game_window import GameWindow, GameWindowService


class _FakeProcess:
    def __init__(self, path):
        self._path = path

    def exe(self):
        return self._path

    def name(self):
        return Path(self._path).name


class GameWindowServiceTests(unittest.TestCase):
    def test_configured_executable_path_selects_its_window_not_same_title(self):
        configured_path = r"C:\Games\BH3\BH3.exe"
        process_paths = {
            101: r"C:\Other\Fake.exe",
            202: configured_path,
        }
        service = GameWindowService(lambda: configured_path)

        def enum_windows(callback, context):
            for hwnd in (11, 22):
                callback(hwnd, context)

        with (
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.EnumWindows",
                side_effect=enum_windows,
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.IsWindow",
                return_value=True,
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.IsWindowVisible",
                return_value=True,
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.GetClientRect",
                return_value=(0, 0, 1280, 720),
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.ClientToScreen",
                return_value=(100, 50),
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.GetWindowText",
                side_effect=lambda hwnd: "崩坏3" if hwnd == 11 else "Honkai Impact 3rd",
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.GetForegroundWindow",
                return_value=11,
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32process.GetWindowThreadProcessId",
                side_effect=lambda hwnd: (1, 101 if hwnd == 11 else 202),
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.psutil.Process",
                side_effect=lambda pid: _FakeProcess(process_paths[pid]),
            ),
        ):
            selected = service.find()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.hwnd, 22)
        self.assertEqual(selected.pid, 202)

    def test_process_name_is_used_when_no_path_is_configured(self):
        service = GameWindowService()
        with (
            mock.patch.object(
                service,
                "_get_process_identity",
                return_value=(r"C:\Games\BH3.exe", "bh3.exe"),
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.IsWindow",
                return_value=True,
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.IsWindowVisible",
                return_value=True,
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.GetClientRect",
                return_value=(0, 0, 1920, 1080),
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.ClientToScreen",
                return_value=(0, 0),
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.GetWindowText",
                return_value="任意标题",
            ),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32process.GetWindowThreadProcessId",
                return_value=(1, 42),
            ),
        ):
            candidate = service._describe_candidate(99)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.pid, 42)

    def test_client_click_is_translated_to_screen_coordinates(self):
        service = GameWindowService()
        window = GameWindow(
            hwnd=88,
            pid=42,
            process_path=r"C:\Games\BH3.exe",
            title="崩坏3",
            client_rect=(300, 200, 1580, 920),
        )
        with (
            mock.patch.object(service, "find", return_value=window),
            mock.patch.object(service, "activate", return_value=True),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32gui.ClientToScreen",
                return_value=(420, 280),
            ),
            mock.patch("bbh3_scan_launch.core.game_window.pyautogui.click") as click,
        ):
            result = service.click_client(120, 80)

        self.assertTrue(result)
        click.assert_called_once_with(420, 280)

    def test_monitor_change_refreshes_capture_from_virtual_desktop(self):
        service = GameWindowService()
        window = GameWindow(
            hwnd=88,
            pid=42,
            process_path=r"C:\Games\BH3.exe",
            title="崩坏3",
            client_rect=(-1600, 100, -320, 820),
        )
        print_window_frame = Image.new("RGB", (8, 8), color=(0, 0, 0))
        desktop_frame = Image.new("RGB", (8, 8), color=(0, 0, 0))
        desktop_frame.putpixel((4, 4), (255, 255, 255))
        service._last_monitor = 1

        with (
            mock.patch.object(service, "find", return_value=window),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32api.MonitorFromWindow",
                return_value=2,
            ),
            mock.patch.object(
                service,
                "_capture_with_print_window",
                return_value=print_window_frame,
            ) as print_capture,
            mock.patch.object(
                service,
                "_capture_from_desktop",
                return_value=desktop_frame,
            ) as desktop_capture,
        ):
            captured = service.capture()

        self.assertIs(captured, desktop_frame)
        desktop_capture.assert_called_once_with(window)
        print_capture.assert_not_called()

    def test_blank_print_window_frame_falls_back_to_virtual_desktop(self):
        service = GameWindowService()
        window = GameWindow(
            hwnd=88,
            pid=42,
            process_path=r"C:\Games\BH3.exe",
            title="崩坏3",
            client_rect=(100, 100, 1380, 820),
        )
        blank_frame = Image.new("RGB", (8, 8), color=(0, 0, 0))
        desktop_frame = Image.new("RGB", (8, 8), color=(0, 0, 0))
        desktop_frame.putpixel((4, 4), (255, 255, 255))

        with (
            mock.patch.object(service, "find", return_value=window),
            mock.patch(
                "bbh3_scan_launch.core.game_window.win32api.MonitorFromWindow",
                return_value=1,
            ),
            mock.patch.object(
                service,
                "_capture_with_print_window",
                return_value=blank_frame,
            ),
            mock.patch.object(
                service,
                "_capture_from_desktop",
                return_value=desktop_frame,
            ),
        ):
            captured = service.capture()

        self.assertIs(captured, desktop_frame)


class ImageProcessorWindowTests(unittest.TestCase):
    def test_templates_scale_to_game_client_height(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "1080p_1.png"
            Image.new("L", (100, 50), color=255).save(template_path)
            processor = ImageProcessor(
                template_dir=temp_dir,
                game_window=mock.Mock(),
            )

            scaled = processor._get_scaled_template("1080p_1.png", 720)

        self.assertEqual(scaled.size, (67, 33))


if __name__ == "__main__":
    unittest.main()
