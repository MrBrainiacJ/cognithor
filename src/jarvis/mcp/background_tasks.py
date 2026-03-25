"""Background Task Manager — long-running shell commands with monitoring.

Enables the Planner to start shell commands in the background, monitor
their progress via 5 health-check methods, and read/tail output logs.

Architecture:
  BackgroundProcessManager: SQLite registry + subprocess spawning
  ProcessMonitor: Async polling loop with 5 verification methods
  6 MCP Tools: start, list, check, read_log, stop, wait
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jarvis.utils.logging import get_logger

if TYPE_CHECKING:
    from jarvis.audit import AuditLogger

log = get_logger(__name__)

__all__ = [
    "BackgroundProcessManager",
    "ProcessMonitor",
    "register_background_tools",
]

# Limits
MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per log file
LOG_CLEANUP_DAYS = 7  # Delete logs of finished jobs older than 7 days
DEFAULT_TIMEOUT = 3600  # 1 hour
DEFAULT_CHECK_INTERVAL = 30  # seconds


# ============================================================================
# SQLite Schema
# ============================================================================

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS background_jobs (
    id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    description TEXT DEFAULT '',
    agent_name TEXT DEFAULT 'jarvis',
    session_id TEXT DEFAULT '',
    channel TEXT DEFAULT '',
    pid INTEGER,
    status TEXT DEFAULT 'running',
    exit_code INTEGER,
    started_at REAL NOT NULL,
    finished_at REAL,
    timeout_seconds INTEGER DEFAULT 3600,
    check_interval INTEGER DEFAULT 30,
    log_file TEXT NOT NULL,
    last_check_at REAL,
    last_output_size INTEGER DEFAULT 0,
    working_dir TEXT DEFAULT ''
);
"""


# ============================================================================
# BackgroundProcessManager
# ============================================================================


class BackgroundProcessManager:
    """Manages background shell processes with SQLite persistence."""

    def __init__(
        self,
        db_path: Path | str,
        log_dir: Path | str,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._audit = audit_logger
        self._processes: dict[str, subprocess.Popen] = {}
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(_SCHEMA)
            # Mark orphaned jobs from previous sessions
            conn.execute(
                "UPDATE background_jobs SET status = 'orphaned' "
                "WHERE status = 'running'"
            )
            conn.commit()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # -- Start --------------------------------------------------------------

    async def start(
        self,
        command: str,
        *,
        description: str = "",
        timeout_seconds: int = DEFAULT_TIMEOUT,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
        working_dir: str = "",
        agent_name: str = "jarvis",
        session_id: str = "",
        channel: str = "",
    ) -> str:
        """Start a command in the background. Returns job_id."""
        job_id = f"bg_{uuid.uuid4().hex[:12]}"
        log_file = self._log_dir / f"{job_id}.log"
        cwd = working_dir or None

        loop = asyncio.get_running_loop()

        def _spawn() -> subprocess.Popen:
            lf = open(log_file, "w", encoding="utf-8", errors="replace")
            kwargs: dict[str, Any] = {
                "stdout": lf,
                "stderr": subprocess.STDOUT,
                "cwd": cwd,
                "start_new_session": True,
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                # start_new_session not supported on Windows with creationflags
                kwargs.pop("start_new_session", None)
            if sys.platform == "win32":
                return subprocess.Popen(command, shell=True, **kwargs)
            else:
                return subprocess.Popen(
                    ["bash", "-c", command], **kwargs
                )

        proc = await loop.run_in_executor(None, _spawn)
        self._processes[job_id] = proc

        with self._conn() as conn:
            conn.execute(
                "INSERT INTO background_jobs "
                "(id, command, description, agent_name, session_id, channel, "
                " pid, status, started_at, timeout_seconds, check_interval, "
                " log_file, last_check_at, last_output_size, working_dir) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    job_id, command, description, agent_name, session_id,
                    channel, proc.pid, "running", time.time(),
                    timeout_seconds, check_interval, str(log_file),
                    time.time(), 0, working_dir or "",
                ),
            )

        if self._audit:
            self._audit.log_tool_call(
                "start_background",
                {"command": command[:200], "job_id": job_id},
                agent_name=agent_name,
                result=f"Started as PID {proc.pid}",
                success=True,
            )

        log.info(
            "background_job_started",
            job_id=job_id,
            pid=proc.pid,
            command=command[:100],
        )
        return job_id

    # -- Query --------------------------------------------------------------

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM background_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_jobs(self, active_only: bool = False) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM background_jobs WHERE status = 'running' "
                    "ORDER BY started_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM background_jobs ORDER BY started_at DESC LIMIT 50"
                ).fetchall()
        return [dict(r) for r in rows]

    # -- Check (single job) -------------------------------------------------

    async def check_job(self, job_id: str) -> dict[str, Any] | None:
        """Check a job's status using multiple verification methods."""
        job = self.get_job(job_id)
        if not job or job["status"] != "running":
            return job

        proc = self._processes.get(job_id)
        now = time.time()
        new_status = None
        exit_code = None

        # Method 1: Process alive check
        if proc is not None:
            retcode = proc.poll()
            if retcode is not None:
                exit_code = retcode
                new_status = "completed" if retcode == 0 else "failed"
        else:
            # Orphaned -- check via OS
            pid = job.get("pid")
            if pid and not self._pid_alive(pid):
                new_status = "orphaned"

        # Method 2: Timeout detection
        if new_status is None:
            elapsed = now - job["started_at"]
            if elapsed > job["timeout_seconds"]:
                await self.stop_job(job_id, force=True)
                new_status = "timeout"

        # Method 3: Output stall detection
        log_path = Path(job["log_file"])
        current_size = log_path.stat().st_size if log_path.exists() else 0
        stalled = False
        if (
            new_status is None
            and job["last_output_size"] == current_size
            and (now - (job["last_check_at"] or now)) > job["check_interval"] * 2
        ):
            stalled = True

        # Update DB
        with self._conn() as conn:
            if new_status:
                conn.execute(
                    "UPDATE background_jobs SET status=?, exit_code=?, "
                    "finished_at=?, last_check_at=?, last_output_size=? "
                    "WHERE id=?",
                    (new_status, exit_code, now, now, current_size, job_id),
                )
                # Cleanup process ref
                self._processes.pop(job_id, None)

                if self._audit:
                    self._audit.log_system(
                        f"Background job {job_id} {new_status} "
                        f"(exit_code={exit_code})",
                    )
            else:
                conn.execute(
                    "UPDATE background_jobs SET last_check_at=?, "
                    "last_output_size=? WHERE id=?",
                    (now, current_size, job_id),
                )

        result = self.get_job(job_id)
        if result and stalled:
            result["_stalled"] = True
        return result

    # -- Stop ---------------------------------------------------------------

    async def stop_job(self, job_id: str, force: bool = False) -> bool:
        """Stop a running job. Returns True if killed."""
        job = self.get_job(job_id)
        if not job or job["status"] != "running":
            return False

        proc = self._processes.get(job_id)
        if proc is not None:
            try:
                if force or sys.platform == "win32":
                    proc.kill()
                else:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
            except OSError:
                pass
        else:
            # Try OS-level kill
            pid = job.get("pid")
            if pid:
                try:
                    if sys.platform == "win32":
                        os.kill(pid, signal.SIGTERM)
                    else:
                        os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass

        self._processes.pop(job_id, None)
        with self._conn() as conn:
            conn.execute(
                "UPDATE background_jobs SET status='killed', finished_at=? "
                "WHERE id=?",
                (time.time(), job_id),
            )

        if self._audit:
            self._audit.log_tool_call(
                "stop_background_job",
                {"job_id": job_id, "force": force},
                result="killed",
                success=True,
            )

        log.info("background_job_killed", job_id=job_id, force=force)
        return True

    # -- Wait ---------------------------------------------------------------

    async def wait_job(
        self, job_id: str, timeout: int = 300
    ) -> dict[str, Any] | None:
        """Wait for a job to complete. Returns final status."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = await self.check_job(job_id)
            if not job or job["status"] != "running":
                return job
            await asyncio.sleep(2)
        return self.get_job(job_id)

    # -- Log reading --------------------------------------------------------

    def read_log(
        self,
        job_id: str,
        *,
        tail: int = 0,
        head: int = 0,
        offset: int = 0,
        limit: int = 100,
        grep: str = "",
    ) -> list[str]:
        """Read log file lines with tail/head/grep support."""
        job = self.get_job(job_id)
        if not job:
            return []
        log_path = Path(job["log_file"])
        if not log_path.exists():
            return []

        try:
            all_lines = log_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except OSError:
            return []

        if grep:
            pattern = re.compile(grep, re.IGNORECASE)
            all_lines = [ln for ln in all_lines if pattern.search(ln)]

        if tail > 0:
            return all_lines[-tail:]
        if head > 0:
            return all_lines[:head]
        return all_lines[offset : offset + limit]

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def cleanup_old_logs(self, max_age_days: int = LOG_CLEANUP_DAYS) -> int:
        """Delete log files for finished jobs older than max_age_days."""
        cutoff = time.time() - max_age_days * 86400
        removed = 0
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, log_file FROM background_jobs "
                "WHERE status != 'running' AND finished_at < ?",
                (cutoff,),
            ).fetchall()
            for row in rows:
                p = Path(row["log_file"])
                if p.exists():
                    p.unlink(missing_ok=True)
                    removed += 1
                conn.execute(
                    "DELETE FROM background_jobs WHERE id = ?", (row["id"],)
                )
        return removed
