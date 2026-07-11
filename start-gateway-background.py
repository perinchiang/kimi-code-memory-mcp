#!/usr/bin/env python3
"""
Start the TencentDB Agent Memory Gateway in the background if not already running.

This script is safe to call repeatedly: it first checks port 8420, and only
spawns a new Gateway process when nothing is listening. It is meant to be
invoked from a Windows startup shortcut (VBS) so the user never sees a terminal.
"""

import os
import socket
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent.resolve()
load_dotenv(SCRIPT_DIR / ".env")

INSTALL_DIR = Path.home() / ".memory-tencentdb" / "tdai-memory-openclaw-plugin"
GATEWAY_SCRIPT = INSTALL_DIR / "src" / "gateway" / "server.ts"


def is_gateway_running(host: str = "127.0.0.1", port: int = 8420) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def main() -> int:
    if is_gateway_running():
        # Already running: exit silently so the startup shortcut never pops up.
        return 0

    required = {
        "TENCENTDB_LLM_API_KEY": os.getenv("TENCENTDB_LLM_API_KEY", ""),
        "TENCENTDB_LLM_BASE_URL": os.getenv("TENCENTDB_LLM_BASE_URL", ""),
        "TENCENTDB_LLM_MODEL": os.getenv("TENCENTDB_LLM_MODEL", ""),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        # Running via pythonw: there is no console. Write a small marker file.
        marker = SCRIPT_DIR / "start-gateway-background.error"
        marker.write_text(
            f"Missing env vars: {', '.join(missing)}\n"
            "Please copy .env.example to .env and fill in your LLM credentials.\n",
            encoding="utf-8",
        )
        return 1

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

    tsx_bin = INSTALL_DIR / "node_modules" / ".bin" / "tsx"
    if sys.platform == "win32":
        tsx_bin = INSTALL_DIR / "node_modules" / ".bin" / "tsx.cmd"

    if not tsx_bin.exists():
        marker = SCRIPT_DIR / "start-gateway-background.error"
        marker.write_text(
            f"tsx not found at {tsx_bin}. Run setup-gateway.py first.\n",
            encoding="utf-8",
        )
        return 1

    log_dir = Path.home() / ".memory-tencentdb" / "memory-tdai" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "gateway.autostart.stdout.log"
    stderr_path = log_dir / "gateway.autostart.stderr.log"

    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )

    with open(stdout_path, "a", encoding="utf-8") as stdout_f, open(
        stderr_path, "a", encoding="utf-8"
    ) as stderr_f:
        subprocess.Popen(
            [str(tsx_bin), str(GATEWAY_SCRIPT)],
            cwd=INSTALL_DIR,
            env=env,
            stdout=stdout_f,
            stderr=stderr_f,
            creationflags=creationflags,
            close_fds=True,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
