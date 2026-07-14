#!/usr/bin/env python3
"""
Start the TencentDB Agent Memory Gateway.

Reads LLM credentials from .env and launches the Node.js sidecar.
Keep this process running in a terminal while you use Kimi Code.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent.resolve()
load_dotenv(SCRIPT_DIR / ".env")

INSTALL_DIR = Path.home() / ".memory-tencentdb" / "tdai-memory-openclaw-plugin"
GATEWAY_SCRIPT = INSTALL_DIR / "src" / "gateway" / "server.ts"

REQUIRED = {
    "TENCENTDB_LLM_API_KEY": os.getenv("TENCENTDB_LLM_API_KEY", ""),
    "TENCENTDB_LLM_BASE_URL": os.getenv("TENCENTDB_LLM_BASE_URL", ""),
    "TENCENTDB_LLM_MODEL": os.getenv("TENCENTDB_LLM_MODEL", ""),
}


def main() -> int:
    if not GATEWAY_SCRIPT.exists():
        print(f"Gateway not found at {GATEWAY_SCRIPT}")
        print("Run: python setup-gateway.py")
        return 1

    missing = [k for k, v in REQUIRED.items() if not v]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}")
        print("Please copy .env.example to .env and fill in your LLM credentials.")
        return 1

    env = os.environ.copy()
    # The standalone Gateway reads TDAI_LLM_* variables directly.
    env["TDAI_LLM_API_KEY"] = REQUIRED["TENCENTDB_LLM_API_KEY"]
    env["TDAI_LLM_BASE_URL"] = REQUIRED["TENCENTDB_LLM_BASE_URL"]
    env["TDAI_LLM_MODEL"] = REQUIRED["TENCENTDB_LLM_MODEL"]

    # Optional: forward gateway auth if set
    gateway_key = os.getenv("TENCENTDB_GATEWAY_API_KEY")
    if gateway_key:
        env["TDAI_GATEWAY_API_KEY"] = gateway_key

    # Forward SiliconFlow embedding credentials so tdai-gateway.yaml can use
    # ${SILICONFLOW_API_KEY} / ${SILICONFLOW_BASE_URL} / ${SILICONFLOW_EMBEDDING_MODEL}.
    siliconflow_key = os.getenv("SILICONFLOW_API_KEY")
    if siliconflow_key:
        env["SILICONFLOW_API_KEY"] = siliconflow_key
    env["SILICONFLOW_BASE_URL"] = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    env["SILICONFLOW_EMBEDDING_MODEL"] = os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")

    # Single-process launch (matches start-gateway-background.py v2): run
    # server.ts via `node --import tsx-loader` directly, skipping tsx's CLI
    # wrapper. One process instead of two, consistent with the background script.
    node_bin = shutil.which("node") or shutil.which("node.exe")
    if sys.platform == "win32" and not node_bin:
        node_bin = str(INSTALL_DIR / "node_modules" / ".bin" / "node.exe")
    if not node_bin:
        print("node not found in PATH. Run setup-gateway.py first.")
        return 1

    tsx_loader = INSTALL_DIR / "node_modules" / "tsx" / "dist" / "loader.mjs"
    tsx_preflight = INSTALL_DIR / "node_modules" / "tsx" / "dist" / "preflight.cjs"
    if not tsx_loader.exists():
        print(f"tsx loader not found at {tsx_loader}. Run setup-gateway.py first.")
        return 1

    cmd = [str(node_bin)]
    if tsx_preflight.exists():
        cmd += ["--require", str(tsx_preflight)]
    cmd += ["--import", tsx_loader.as_uri(), str(GATEWAY_SCRIPT)]

    print(f"Starting TencentDB Agent Memory Gateway...")
    print(f"  Base URL: {REQUIRED['TENCENTDB_LLM_BASE_URL']}")
    print(f"  Model: {REQUIRED['TENCENTDB_LLM_MODEL']}")
    print(f"  Gateway: http://127.0.0.1:8420")
    print("Press Ctrl+C to stop.\n")

    try:
        subprocess.run(cmd, cwd=INSTALL_DIR, env=env, check=True)
    except KeyboardInterrupt:
        print("\nGateway stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
