"""Build a standalone DecodeMRI app with PyInstaller."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

APP_NAME = "DecodeMRI"
APP_PATH = Path("dist") / f"{APP_NAME}.app"


def _project_version() -> str:
    with Path("pyproject.toml").open("rb") as project_file:
        project = tomllib.load(project_file)
    return str(project["project"]["version"])


def _set_plist_value(plist_path: Path, key: str, value: str) -> None:
    set_result = subprocess.run(
        ["/usr/libexec/PlistBuddy", "-c", f"Set :{key} {value}", str(plist_path)],
        check=False,
    )
    if set_result.returncode != 0:
        subprocess.run(
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                f"Add :{key} string {value}",
                str(plist_path),
            ],
            check=True,
        )


def main() -> int:
    """Run PyInstaller with a conservative default configuration."""

    icon_path = "assets/icons/medreport_icon.png"
    version = _project_version()
    command = [
        "pyinstaller",
        "--name",
        APP_NAME,
        "--windowed",
        "--noconfirm",
        "--clean",
        "--osx-bundle-identifier",
        "com.adibsouly.decodemri",
        "--icon",
        icon_path,
        "--add-data",
        "assets:assets",
        "apps/desktop/main.py",
    ]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        return result.returncode

    plist_path = APP_PATH / "Contents" / "Info.plist"
    _set_plist_value(plist_path, "CFBundleShortVersionString", version)
    _set_plist_value(plist_path, "CFBundleVersion", version)

    signing_identity = os.environ.get("MEDREPORT_CODESIGN_IDENTITY", "-")
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", signing_identity, str(APP_PATH)],
        check=True,
    )

    archive_path = Path("dist") / f"DecodeMRI-macOS-arm64-v{version}.zip"
    archive_path.unlink(missing_ok=True)
    subprocess.run(
        [
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(APP_PATH),
            str(archive_path),
        ],
        check=True,
    )
    print(f"Created {APP_PATH}")
    print(f"Created {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
