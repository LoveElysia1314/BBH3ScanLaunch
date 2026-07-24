import unittest

from bbh3_scan_launch.core.services.update_service import UpdateService
from bbh3_scan_launch.utils.version_utils import parse_version


class FakeVersionManager:
    def __init__(self, current="1.2.3"):
        self.current = current

    def get_version_info(self, key):
        assert key == "current"
        return self.current


class FakeSourceManager:
    def __init__(self):
        self.version_info = {
            "download_url": {
                "gitee": "https://example.test/gitee",
                "github": "https://example.test/github",
            }
        }

    def get_links_by_category(self, category):
        return self.version_info.get(category, {})

    @staticmethod
    def get_priority_order():
        return ["gitee", "github"]


class FakeNetworkManager:
    def __init__(self, remote="1.2.4", fetch_success=True):
        self.remote = remote
        self.fetch_success = fetch_success
        self.fetch_calls = []
        self.source_manager = FakeSourceManager()

    def get_remote_version_info(self, source=None):
        return {"app_info": {"version": self.remote}}

    def fetch_remote_files(self, source=None, should_update_files=True):
        self.fetch_calls.append((source, should_update_files))
        return self.fetch_success

    @staticmethod
    def try_download_by_priority(source_priority=None):
        return True


class VersionParsingTests(unittest.TestCase):
    def test_parse_version_accepts_common_variants(self):
        self.assertEqual(parse_version("v1.2"), (1, 2, 0))
        self.assertEqual(parse_version("1.2.3-beta.4"), (1, 2, 3))
        self.assertEqual(parse_version(None), (0, 0, 0))


class UpdateServiceTests(unittest.TestCase):
    def test_newer_version_refreshes_metadata_and_selects_download(self):
        network = FakeNetworkManager(remote="1.3.0")
        result = UpdateService(FakeVersionManager(), network).check_update()

        self.assertTrue(result["has_update"])
        self.assertEqual(result["download_url"], "https://example.test/gitee")
        self.assertEqual(network.fetch_calls, [(None, True)])

    def test_older_remote_version_does_not_overwrite_local_files(self):
        network = FakeNetworkManager(remote="1.1.9")
        result = UpdateService(FakeVersionManager(), network).check_update()

        self.assertFalse(result["has_update"])
        self.assertEqual(network.fetch_calls, [])

    def test_refresh_failure_is_reported(self):
        network = FakeNetworkManager(fetch_success=False)
        result = UpdateService(FakeVersionManager(), network).check_update()

        self.assertEqual(result["error"], "无法更新本地文件")


if __name__ == "__main__":
    unittest.main()
