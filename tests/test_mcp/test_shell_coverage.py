"""Coverage-Tests fuer shell.py -- fehlende Pfade abdecken."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.mcp.shell import ShellTools, ShellError, register_shell_tools


@pytest.fixture
def config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.workspace_dir = tmp_path
    cfg.shell = None
    cfg.sandbox_level = "bare"
    cfg.sandbox_network = "allow"
    cfg.security.shell_validate_paths = True
    return cfg


class TestValidateCommand:
    def test_null_byte_blocked(self) -> None:
        result = ShellTools._validate_command("echo \x00test", "/tmp")
        assert result is not None
        assert "Null-Byte" in result

    def test_path_traversal_warning(self) -> None:
        # Path traversal should warn but not block
        result = ShellTools._validate_command("cat ../../etc/passwd", "/workspace")
        assert result is None  # Not blocked, just warned

    def test_normal_command(self) -> None:
        result = ShellTools._validate_command("ls -la", "/workspace")
        assert result is None

    def test_unparsable_command(self) -> None:
        result = ShellTools._validate_command("echo 'unterminated", "/workspace")
        assert result is None

    def test_file_command_escape(self) -> None:
        result = ShellTools._validate_command("cat /etc/passwd", "/workspace")
        assert result is None  # Warns but does not block


class TestExecCommand:
    @pytest.mark.asyncio
    async def test_empty_command(self, config: MagicMock) -> None:
        shell = ShellTools(config)
        result = await shell.exec_command("   ")
        assert "Kein Befehl" in result

    @pytest.mark.asyncio
    async def test_outside_workspace(self, config: MagicMock) -> None:
        shell = ShellTools(config)
        result = await shell.exec_command("ls", working_dir="/etc")
        assert "Zugriff verweigert" in result

    @pytest.mark.asyncio
    async def test_null_byte_blocked(self, config: MagicMock) -> None:
        shell = ShellTools(config)
        result = await shell.exec_command("echo \x00test")
        assert "Null-Byte" in result

    @pytest.mark.asyncio
    async def test_redacted_logging(self, config: MagicMock) -> None:
        shell = ShellTools(config)
        # Just verify it doesn't crash on sensitive commands
        mock_result = MagicMock()
        mock_result.output = "ok"
        mock_result.exit_code = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""
        mock_result.timed_out = False
        mock_result.truncated = False
        mock_result.sandbox_level = "bare"
        shell._sandbox.execute = AsyncMock(return_value=mock_result)
        result = await shell.exec_command("export API_KEY=secret123")
        assert result == "ok"


class TestSandboxLevel:
    def test_property(self, config: MagicMock) -> None:
        shell = ShellTools(config)
        assert isinstance(shell.sandbox_level, str)


class TestRegisterShellTools:
    def test_registers_one_tool(self, config: MagicMock) -> None:
        mock_client = MagicMock()
        shell = register_shell_tools(mock_client, config)
        assert isinstance(shell, ShellTools)
        assert mock_client.register_builtin_handler.call_count == 1
        name = mock_client.register_builtin_handler.call_args_list[0].args[0]
        assert name == "exec_command"
