#!/usr/bin/env python3
"""The source formatter must not leave partially formatted files on failure."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/format_code.py"


class FormatterSafety(unittest.TestCase):
    def test_no_partial_writes_when_later_formatter_fails(self):
        source = ROOT / "CMakeLists.txt"
        original = source.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            cmake_formatter = folder / "fake-cmake-format"
            cmake_formatter.write_text(
                "#!/usr/bin/env python3\nprint('# changed in the staging pass')\n"
            )
            cmake_formatter.chmod(0o755)
            black = folder / "black"
            black.write_text("#!/usr/bin/env python3\nraise SystemExit(7)\n")
            black.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(folder) + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--cmake-format",
                    str(cmake_formatter),
                    "--path",
                    "CMakeLists.txt",
                    "--path",
                    "tests/elf_revision.py",
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("returned non-zero exit status 7", result.stderr)
            self.assertEqual(source.read_bytes(), original)

    def test_unknown_path_is_rejected(self):
        env = os.environ.copy()
        env["PATH"] = ""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--path", "../escape.cpp"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a tracked or nonignored source file", result.stderr)

    def test_source_archive_without_git_or_ripgrep(self):
        import shutil
        import tarfile

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            scripts = folder / "scripts"
            scripts.mkdir()
            for name in ("format_code.py", "package_source.py", "source_files.py"):
                shutil.copy2(ROOT / "scripts" / name, scripts / name)
            (folder / "sample.json").write_text('{"x":1}')
            for name in ("build", "build-san", "cmake-build-debug", ".aws"):
                (folder / name).mkdir()
                (folder / name / "excluded.json").write_text("invalid JSON")
            env = os.environ.copy()
            env["PATH"] = ""
            result = subprocess.run(
                [
                    sys.executable,
                    str(scripts / "format_code.py"),
                    "--path",
                    "sample.json",
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((folder / "sample.json").read_text(), '{\n  "x": 1\n}\n')
            archives = [folder / "build" / f"source{i}.tar.gz" for i in (1, 2)]
            for archive in archives:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(scripts / "package_source.py"),
                        "--update-checksums",
                        "--output",
                        str(archive),
                    ],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(archives[0].read_bytes(), archives[1].read_bytes())
            with tarfile.open(archives[0]) as archive:
                self.assertEqual(
                    set(archive.getnames()),
                    {
                        "mica-sdk-2.0/sample.json",
                        "mica-sdk-2.0/SHA256SUMS",
                        *(
                            f"mica-sdk-2.0/scripts/{name}"
                            for name in (
                                "format_code.py",
                                "package_source.py",
                                "source_files.py",
                            )
                        ),
                    },
                )

    def test_missing_hdl_tools_invalidate_previous_verification(self):
        import json

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            results = folder / "validation/results.json"
            results.parent.mkdir()
            results.write_text('[{"name":"software","exit":0}]\n')
            env = os.environ.copy()
            env["PATH"] = ""
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/verify.py"),
                    "--all",
                    "--build-dir",
                    str(folder),
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing required --all tools", result.stderr)
            self.assertEqual(json.loads(results.read_text()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
