"""Cognithor agent pack plugin system.

Public API (wired up as submodules land in tasks 2.2-2.4):

- ``AgentPack`` — abstract base class packs inherit from
- ``PackManifest`` — validated manifest model
- ``PackContext`` — facade exposing the subset of Gateway state a pack may touch
- ``PackLoader`` — discovers + loads packs from ``~/.cognithor/packs/``
- ``PackInstaller`` — installs/upgrades/removes packs from zip files or URLs
- ``PackLoadError``, ``PackInstallError``, ``PackValidationError`` — exception types
"""

from __future__ import annotations

from cognithor.packs.errors import (
    PackError,
    PackInstallError,
    PackLoadError,
    PackValidationError,
)

__all__ = [
    "PackError",
    "PackInstallError",
    "PackLoadError",
    "PackValidationError",
]
