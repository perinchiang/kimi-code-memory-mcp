#!/usr/bin/env python3
"""
Start the TencentDB Agent Memory Gateway in the background if not already running.

v2 — truly invisible background launcher.

Why v2: the original launcher ran `node tsx/dist/cli.mjs server.ts`. tsx's CLI is
itself a *wrapper* that spawns a second `node` child process to actually execute
server.ts. On Windows that second node process was not created with
window-hiding flags, so it popped up a visible console — and closing that
console killed the real gateway.

Fix: launch server.ts with the SAME command tsx uses internally
(`node --require preflight.cjs --import loader.mjs server.ts`) as a SINGLE
process. The Popen flags (CREATE_NO_WINDOW + SW_HIDE) then fully cover the only
node process that exists, so there is nothing visible to close.

This script is safe to call repeatedly: it first probes port 8420 and only
spawns a new Gateway when nothing is listening. Designed to be invoked from a
Windows startup shortcut (VBS) so the user never sees a terminal.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent.resolve()
load_dotenv(SCRIPT_DIR / ".env")

INSTALL_DIR = Path.home() / ".memory-tencentdb" / "tdai-memory-openclaw-plugin"
GATEWAY_SCRIPT = INSTALL_DIR / "src" / "gateway" / "server.ts"
TSX_LOADER = INSTALL_DIR / "node_modules" / "tsx" / "dist" / "loader.mjs"
TSX_PREFLIGHT = INSTALL_DIR / "node_modules" / "tsx" / "dist" / "preflight.cjs"

HOST = "127.0.0.1"
PORT = 8420
PID_FILE = Path.home() / ".memory-tencentdb" / "gateway.v2.pid"
STARTUP_TIMEOUT = 45  # seconds to wait for the port to come up


def is_gateway_running(host: str = HOST, port: int = PORT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def write_error(msg: str) -> None:
    """pythonw has no console — record failures to a marker file."""
    marker = SCRIPT_DIR / "start-gateway-background.error"
    marker.write_text(msg, encoding="utf-8")


def build_env() -> dict:
    required = {
        "TENCENTDB_LLM_API_KEY": os.getenv("TENCENTDB_LLM_API_KEY", ""),
        "TENCENTDB_LLM_BASE_URL": os.getenv("TENCENTDB_LLM_BASE_URL", ""),
        "TENCENTDB_LLM_MODEL": os.getenv("TENCENTDB_LLM_MODEL", ""),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing env vars: {', '.join(missing)}\n"
            "Please copy .env.example to .env and fill in your LLM credentials.\n"
        )

    env = os.environ.copy()
    env["TDAI_LLM_API_KEY"] = required["TENCENTDB_LLM_API_KEY"]
    env["TDAI_LLM_BASE_URL"] = required["TENCENTDB_LLM_BASE_URL"]
    env["TDAI_LLM_MODEL"] = required["TENCENTDB_LLM_MODEL"]

    gateway_key = os.getenv("TENCENTDB_GATEWAY_API_KEY")
    if gateway_key:
        env["TDAI_GATEWAY_API_KEY"] = gateway_key

    siliconflow_key = os.getenv("SILICONFLOW_API_KEY")
    if siliconflow_key:
        env["SILICONFLOW_API_KEY"] = siliconflow_key
    env["SILICONFLOW_BASE_URL"] = os.getenv(
        "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"
    )
    env["SILICONFLOW_EMBEDDING_MODEL"] = os.getenv(
        "SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3"
    )
    return env


def resolve_node() -> str | None:
    node_bin = shutil.which("node") or shutil.which("node.exe")
    if sys.platform == "win32" and not node_bin:
        node_bin = str(INSTALL_DIR / "node_modules" / ".bin" / "node.exe")
    return node_bin


def main() -> int:
    if is_gateway_running():
        # Already running: exit silently so the startup shortcut never pops up.
        return 0

    # Clear any stale error marker from a previous failed run.
    stale = SCRIPT_DIR / "start-gateway-background.error"
    if stale.exists():
        stale.unlink()

    try:
        env = build_env()
    except RuntimeError as exc:
        write_error(str(exc))
        return 1

    node_bin = resolve_node()
    if not node_bin:
        write_error("node not found in PATH. Run setup-gateway.py first.\n")
        return 1

    if not GATEWAY_SCRIPT.exists():
        write_error(f"Gateway script not found at {GATEWAY_SCRIPT}. Run setup-gateway.py first.\n")
        return 1

    if not TSX_LOADER.exists():
        write_error(f"tsx loader not found at {TSX_LOADER}. Run setup-gateway.py first.\n")
        return 1

    # Single-process launch — the exact invocation tsx's CLI uses internally,
    # minus the cli.mjs wrapper. One node process = one window to hide.
    loader_url = TSX_LOADER.as_uri()
    cmd = [str(node_bin)]
    if TSX_PREFLIGHT.exists():
        cmd += ["--require", str(TSX_PREFLIGHT)]
    cmd += ["--import", loader_url, str(GATEWAY_SCRIPT)]

    log_dir = Path.home() / ".memory-tencentdb" / "memory-tdai" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "gateway.autostart.stdout.log"
    stderr_path = log_dir / "gateway.autostart.stderr.log"

    creationflags = 0
    startupinfo = None
    if sys.platform == "win32":
        # CREATE_NO_WINDOW is the reliable flag for hiding node.exe consoles on
        # Windows (DETACHED_PROCESS still lets node AllocConsole a visible window
        # in some cases). CREATE_NEW_PROCESS_GROUP detaches Ctrl+C signalling so
        # closing any parent terminal does not kill the gateway.
        creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    with open(stdout_path, "a", encoding="utf-8") as stdout_f, open(
        stderr_path, "a", encoding="utf-8"
    ) as stderr_f:
        proc = subprocess.Popen(
            cmd,
            cwd=INSTALL_DIR,
            env=env,
            stdout=stdout_f,
            stderr=stderr_f,
            stdin=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=creationflags,
            close_fds=True,
        )

    try:
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    except OSError:
        pass  # PID file is a convenience, not critical.

    # Wait for the port to come up so callers know the gateway is ready.
    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        if is_gateway_running():
            return 0
        if proc.poll() is not None:
            write_error(
                f"Gateway exited immediately with code {proc.returncode}.\n"
                f"See stderr log: {stderr_path}\n"
            )
            return 1
        time.sleep(1)

    # Port did not come up within the timeout but the process is still alive.
    # Let it keep running — it may just be slow to bind.
    return 0


if __name__ == "__main__":
    sys.exit(main())
