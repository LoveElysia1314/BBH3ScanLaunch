import json
import tempfile
import unittest
from pathlib import Path

from bbh3_scan_launch.utils.config_utils import ConfigManager


class ConfigManagerPersistenceTests(unittest.TestCase):
    def test_legacy_install_config_is_migrated_to_user_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "install" / "config" / "config.json"
            target = root / "local-app-data" / "config.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                json.dumps({"game_path": r"D:\Games\BH3.exe"}),
                encoding="utf-8",
            )

            manager = ConfigManager(
                config_path=target,
                legacy_paths=(legacy,),
            )

            self.assertEqual(manager.get_config("game_path"), r"D:\Games\BH3.exe")
            self.assertTrue(target.is_file())
            self.assertTrue(legacy.is_file())

    def test_existing_user_config_is_not_overwritten_by_legacy_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "legacy.json"
            target = root / "user" / "config.json"
            target.parent.mkdir(parents=True)
            legacy.write_text(
                json.dumps({"game_path": "legacy"}),
                encoding="utf-8",
            )
            target.write_text(
                json.dumps({"game_path": "persistent"}),
                encoding="utf-8",
            )

            manager = ConfigManager(
                config_path=target,
                legacy_paths=(legacy,),
            )

            self.assertEqual(manager.get_config("game_path"), "persistent")

    def test_writes_remain_in_user_data_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "user" / "config.json"
            manager = ConfigManager(config_path=target, legacy_paths=())

            manager.set_config("auto_clip", True)

            saved = json.loads(target.read_text(encoding="utf-8"))
            self.assertTrue(saved["auto_clip"])


if __name__ == "__main__":
    unittest.main()
