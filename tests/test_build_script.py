import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BUILD_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build.py"
SPEC = importlib.util.spec_from_file_location("build_script", BUILD_SCRIPT_PATH)
build_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_script)


class BuildScriptTests(unittest.TestCase):
    def test_default_arguments_reuse_build_environment(self):
        args = build_script.parse_args([])
        self.assertFalse(args.recreate_build_env)
        self.assertFalse(args.refresh_deps)
        self.assertFalse(args.skip_installer)
        self.assertFalse(args.rebuild)
        self.assertEqual(args.timeout, 1800)

    def test_build_environment_uses_dedicated_python(self):
        config = build_script.BuildConfig()
        self.assertEqual(config.bootstrap_python, Path(sys.executable))
        self.assertIn(".build-venv", str(config.python_exe))

    def test_build_environment_is_created_then_reused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "requirements.txt").write_text("requests\n", encoding="utf-8")
            config = build_script.BuildConfig(project_root=root)
            calls = []

            def fake_run(label, *_args, **_kwargs):
                calls.append(label)
                if label == "创建构建虚拟环境":
                    config.python_exe.parent.mkdir(parents=True, exist_ok=True)
                    config.python_exe.touch()

            with mock.patch.object(build_script, "run_command", side_effect=fake_run):
                build_script.ensure_build_environment(config)
                build_script.ensure_build_environment(config)

            self.assertEqual(calls.count("创建构建虚拟环境"), 1)
            self.assertEqual(calls.count("安装构建依赖"), 1)
            self.assertEqual(calls.count("检查构建依赖"), 2)

    def test_run_command_reports_nonzero_exit_as_runtime_error(self):
        with self.assertRaisesRegex(RuntimeError, "退出码 3"):
            build_script.run_command(
                "失败测试",
                [sys.executable, "-c", "raise SystemExit(3)"],
                timeout=5,
            )

    def test_run_command_enforces_timeout(self):
        with self.assertRaisesRegex(RuntimeError, "超时"):
            build_script.run_command(
                "超时测试",
                [sys.executable, "-c", "import time; time.sleep(1)"],
                timeout=0.05,
            )

    def test_pyinstaller_command_uses_isolated_python(self):
        config = build_script.BuildConfig()
        command = build_script.build_pyinstaller_command(
            config,
            Path("spec"),
            Path("pyzbar"),
        )
        command_text = " ".join(str(part) for part in command)
        self.assertEqual(command[0], str(config.python_exe))
        self.assertNotIn("--exclude-module torch", command_text)
        self.assertNotIn("PYTHONUTF8", command_text)

    def test_installer_script_uses_current_architecture_identifier(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "scripts").mkdir()
            config = build_script.BuildConfig(project_root=root)

            iss_path = build_script.generate_iss_file(config)
            content = iss_path.read_text(encoding="utf-8")

            self.assertIn("ArchitecturesAllowed=x64compatible", content)
            self.assertIn(
                "ArchitecturesInstallIn64BitMode=x64compatible",
                content,
            )
            self.assertNotIn("ArchitecturesAllowed=x64\n", content)
            self.assertIn("function PrepareToInstall", content)
            self.assertIn(
                r"{localappdata}\BBH3ScanLaunch",
                content,
            )
            self.assertIn("CopyFile(legacyConfigPath", content)

    def test_pyinstaller_fingerprint_changes_with_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "scripts").mkdir()
            (root / "src").mkdir()
            (root / "requirements.txt").write_text("requests\n", encoding="utf-8")
            (root / "run.py").write_text("print('run')\n", encoding="utf-8")
            (root / "BHimage.ico").write_bytes(b"icon")
            (root / "scripts" / "build.py").write_text(
                "USE_ONEFILE = False\n", encoding="utf-8"
            )
            source = root / "src" / "app.py"
            source.write_text("VALUE = 1\n", encoding="utf-8")
            config = build_script.BuildConfig(project_root=root)

            before = build_script.calculate_pyinstaller_fingerprint(
                config, environment_identity="packages"
            )
            source.write_text("VALUE = 2\n", encoding="utf-8")
            after = build_script.calculate_pyinstaller_fingerprint(
                config, environment_identity="packages"
            )

            self.assertNotEqual(before, after)

    def test_pyinstaller_fingerprint_ignores_generated_bytecode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "scripts").mkdir()
            source_dir = root / "src" / "package"
            source_dir.mkdir(parents=True)
            (root / "requirements.txt").write_text("", encoding="utf-8")
            (root / "run.py").write_text("", encoding="utf-8")
            (root / "BHimage.ico").write_bytes(b"icon")
            (root / "scripts" / "build.py").write_text("", encoding="utf-8")
            (source_dir / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
            config = build_script.BuildConfig(project_root=root)

            before = build_script.calculate_pyinstaller_fingerprint(
                config, environment_identity="packages"
            )
            bytecode = source_dir / "__pycache__" / "module.pyc"
            bytecode.parent.mkdir()
            bytecode.write_bytes(b"generated-bytecode")
            after = build_script.calculate_pyinstaller_fingerprint(
                config, environment_identity="packages"
            )

            self.assertEqual(before, after)

    def test_pyinstaller_output_is_reused_when_hash_matches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = build_script.BuildConfig(project_root=root)
            build_calls = []

            def fake_build(_config):
                build_calls.append(True)
                executable = config.app_dir / config.exe_name
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.write_bytes(b"exe")

            with (
                mock.patch.object(
                    build_script,
                    "calculate_pyinstaller_fingerprint",
                    return_value="stable-hash",
                ),
                mock.patch.object(
                    build_script,
                    "run_pyinstaller_build",
                    side_effect=fake_build,
                ),
            ):
                first = build_script.build_or_reuse_pyinstaller(config)
                second = build_script.build_or_reuse_pyinstaller(config)

            self.assertTrue(first)
            self.assertFalse(second)
            self.assertEqual(len(build_calls), 1)

    def test_pyinstaller_command_overwrites_unlocked_stale_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = build_script.BuildConfig(project_root=root)
            command = build_script.build_pyinstaller_command(
                config,
                root / "spec",
                root / "pyzbar",
            )

            self.assertIn("--noconfirm", command)

    def test_clean_build_cache_reports_locked_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = build_script.BuildConfig(project_root=Path(temp_dir))
            locked_dist = config.output_dir
            locked_dist.mkdir(parents=True)

            with (
                mock.patch.object(build_script.shutil, "rmtree"),
                self.assertRaisesRegex(RuntimeError, "关闭正在运行"),
            ):
                build_script.clean_build_cache(config)


if __name__ == "__main__":
    unittest.main()
