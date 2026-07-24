import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bbh3_scan_launch.core.app_bootstrap import AppBootstrap
from bbh3_scan_launch.core.runtime_context import RuntimeContext
from bbh3_scan_launch.gui.application_window import ApplicationWindow


class BootstrapSmokeTests(unittest.TestCase):
    def test_window_composition(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            mock.patch.dict(
                os.environ,
                {"BBH3SCANLAUNCH_DATA_DIR": temp_dir},
            ),
        ):
            context = RuntimeContext.build()
            bundle = AppBootstrap(context)._build_window_and_coordinator([])
            try:
                self.assertIsInstance(bundle.window, ApplicationWindow)
                self.assertIs(bundle.coordinator.window, bundle.window)
                self.assertIs(bundle.coordinator.app, bundle.app)
                self.assertIs(
                    context.game_manager._game_window,
                    context.image_processor.game_window,
                )
            finally:
                bundle.window.close()
                bundle.app.quit()


if __name__ == "__main__":
    unittest.main()
