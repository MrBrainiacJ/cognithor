"""Auto-upgrade Cognithor if a source tree with a newer version is found.

Checked locations (in order):
  1. COGNITHOR_DEV environment variable
  2. %USERPROFILE%\Jarvis\jarvis complete v20
  3. D:\Jarvis\jarvis complete v20
  4. %USERPROFILE%\cognithor

If a pyproject.toml with a higher version is found, upgrades via pip install
(--no-deps to avoid breaking the embedded environment).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def _read_version_from_toml(toml_path: Path) -> str | None:
    """Extract version = 'X.Y.Z' from pyproject.toml."""
    try:
        for line in toml_path.read_text(encoding="utf-8").splitlines():
            m = re.match(r'\s*version\s*=\s*"([^"]+)"', line)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def _installed_version() -> str | None:
    """Get the currently installed jarvis version."""
    try:
        from jarvis import __version__

        return __version__
    except Exception:
        return None


def _compare_versions(a: str, b: str) -> int:
    """Compare two version strings. Returns >0 if a > b."""

    def parts(v: str) -> list[int]:
        return [int(x) for x in re.findall(r"\d+", v)]

    pa, pb = parts(a), parts(b)
    for x, y in zip(pa, pb):
        if x != y:
            return x - y
    return len(pa) - len(pb)


def main() -> None:
    candidates = []

    # 1. COGNITHOR_DEV env var
    dev = os.environ.get("COGNITHOR_DEV", "")
    if dev:
        candidates.append(Path(dev))

    # 2-4. Common locations
    home = Path.home()
    candidates.extend(
        [
            home / "Jarvis" / "jarvis complete v20",
            Path("D:/Jarvis/jarvis complete v20"),
            home / "cognithor",
        ]
    )

    cur = _installed_version()
    if not cur:
        return

    for candidate in candidates:
        toml = candidate / "pyproject.toml"
        if not toml.exists():
            continue

        dev_ver = _read_version_from_toml(toml)
        if not dev_ver:
            continue

        if _compare_versions(dev_ver, cur) > 0:
            print(f"  [UPGRADE] Source v{dev_ver} found at {candidate}")
            print(f"            Installed v{cur} -- upgrading...")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    str(candidate),
                    "--no-deps",
                    "--quiet",
                    "--disable-pip-version-check",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print(f"  [OK] Upgraded to v{dev_ver}")
            else:
                print(f"  [WARN] Upgrade failed: {result.stderr.strip()[:200]}")
                print(f"         Continuing with v{cur}")
            return  # Only upgrade once

    # No upgrade needed — silent return


if __name__ == "__main__":
    main()
