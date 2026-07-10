"""Build a standalone MedReport app with PyInstaller."""

from __future__ import annotations

import subprocess


def main() -> int:
    """Run PyInstaller with a conservative default configuration."""

    icon_path = "assets/icons/medreport_icon.png"
    command = [
        "pyinstaller",
        "--name",
        "MedReport",
        "--windowed",
        "--noconfirm",
        "--icon",
        icon_path,
        "--add-data",
        "assets:assets",
        "--collect-all",
        "PySide6",
        "apps/desktop/main.py",
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
