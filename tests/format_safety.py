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
            self.assertEqual(source.read_bytes(), original)

    def test_unknown_path_is_rejected(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--path", "../escape.cpp"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a tracked or nonignored source file", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
