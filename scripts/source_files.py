"""Discover distributable sources without requiring ripgrep or a Git checkout."""

import os
from pathlib import Path
import shutil
import subprocess


def excluded_directory(name):
    return name in {
        ".git",
        ".aws",
        ".codex",
        ".agents",
        "__pycache__",
        ".venv",
        ".pytest_cache",
    } or name.startswith(("build", "cmake-build-"))


def source_files(root):
    root = Path(root)
    if (root / ".git").exists() and shutil.which("git"):
        names = (
            subprocess.check_output(
                ["git", "ls-files", "-c", "-o", "--exclude-standard", "-z"], cwd=root
            )
            .decode()
            .split("\0")
        )
    else:
        names = []
        for directory, folders, files in os.walk(root, followlinks=False):
            folders[:] = [name for name in folders if not excluded_directory(name)]
            names.extend(
                str((Path(directory) / name).relative_to(root)) for name in files
            )
    return sorted(
        {
            name
            for name in names
            if name
            and not any(excluded_directory(part) for part in Path(name).parts[:-1])
        }
    )
