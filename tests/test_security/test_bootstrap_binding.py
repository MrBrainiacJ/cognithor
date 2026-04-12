"""Regression tests for bootstrap token binding (GHSA-cognithor-001).

The old ``/api/v1/bootstrap`` endpoint leaked the API token without auth.
After the fix the token is injected via ``<meta name="cognithor-token">``
in index.html at startup.  These tests assert:

1. The bootstrap endpoint (if still present) is consumed-once / protected.
2. ``__main__.py`` uses meta-tag injection, not an HTTP endpoint.
"""

from __future__ import annotations

import re
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "cognithor"


class TestBootstrapEndpointProtection:
    """No unprotected route may leak the token."""

    def test_token_not_in_unprotected_routes(self) -> None:
        source = (_SRC / "channels" / "config_routes.py").read_text(
            encoding="utf-8",
        )
        # "bootstrap" must NOT appear in config_routes.py at all.
        # If it ever does, it must be behind ``dependencies=deps`` or
        # return "consumed" (the legacy already-consumed guard).
        matches = [line for line in source.splitlines() if "bootstrap" in line.lower()]
        for line in matches:
            assert (
                "dependencies" in line
                or "consumed" in line.lower()
                or line.lstrip().startswith("#")
                or line.lstrip().startswith('"""')
            ), f"Unprotected 'bootstrap' reference in config_routes.py: {line!r}"


class TestMetaTagInjection:
    """__main__.py must inject the token via <meta> tag, not an endpoint."""

    def test_main_uses_meta_tag_injection(self) -> None:
        source = (_SRC / "__main__.py").read_text(encoding="utf-8")

        # The meta-tag name used by the Flutter frontend.
        assert "cognithor-token" in source, "__main__.py must reference 'cognithor-token' meta tag"

        # Token injection happens via string replacement in HTML.
        assert ".replace(" in source or "replace(" in source, (
            "__main__.py must inject the token via string replacement"
        )

        # The meta tag pattern must exist.
        assert re.search(
            r'<meta\s+name="cognithor-token"',
            source,
        ), '__main__.py must contain the <meta name="cognithor-token"> tag'

        # The old endpoint may still exist (consumed-once guard) but the
        # primary mechanism MUST be meta-tag injection, not an endpoint.
        # Verify the comment referencing GHSA-cognithor-001 is present.
        assert "GHSA-cognithor-001" in source, (
            "__main__.py must reference GHSA-cognithor-001 security advisory"
        )
