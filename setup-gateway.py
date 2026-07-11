#!/usr/bin/env python3
"""
One-time setup for the TencentDB Agent Memory Gateway.

This script:
1. Creates ~/.memory-tencentdb
2. Installs the @tencentdb-agent-memory/memory-tencentdb package
3. Installs tsx (TypeScript executor)
4. Prints the command to start the Gateway
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

INSTALL_DIR = Path.home() / ".memory-tencentdb" / "tdai-memory-openclaw-plugin"


def find_npm() -> str:
    """Find npm executable robustly on Windows, macOS and Linux."""
    npm = shutil.which("npm") or shutil.which("npm.cmd") or shutil.which("npm.ps1")
    if npm:
        return npm

    # Common fallback paths
    candidates = []
    if sys.platform == "win32":
        candidates = [
            Path(r"C:\Program Files\nodejs\npm.cmd"),
            Path(r"C:\Program Files (x86)\nodejs\npm.cmd"),
            Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
        ]
    elif sys.platform == "darwin":
        candidates = [
            Path("/usr/local/bin/npm"),
            Path("/opt/homebrew/bin/npm"),
        ]
    else:
        candidates = [
            Path("/usr/local/bin/npm"),
            Path("/usr/bin/npm"),
        ]

    for c in candidates:
        if c.exists():
            return str(c)

    raise FileNotFoundError(
        "npm not found. Please install Node.js or add npm to PATH."
    )


def run(cmd: list[str], cwd: Path | None = None) -> None:
    npm = find_npm()
    # Replace plain "npm" with resolved executable
    if cmd[0] == "npm":
        cmd[0] = npm
    print(f"> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    print("Setting up TencentDB Agent Memory Gateway...")

    if INSTALL_DIR.exists():
        print(f"Removing old install at {INSTALL_DIR}")
        shutil.rmtree(INSTALL_DIR)

    INSTALL_DIR.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = Path.home() / ".memory-tencentdb" / "_tmp_install"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # npm init -y
        run(["npm", "init", "-y", "--silent"], cwd=temp_dir)
        # install the plugin
        run(
            ["npm", "install", "@tencentdb-agent-memory/memory-tencentdb@latest", "--omit=dev"],
            cwd=temp_dir,
        )
        # install tsx
        run(["npm", "install", "tsx", "--omit=dev"], cwd=temp_dir)

        # Copy plugin contents to final location
        plugin_source = temp_dir / "node_modules" / "@tencentdb-agent-memory" / "memory-tencentdb"
        shutil.copytree(plugin_source, INSTALL_DIR)

        # Copy the full node_modules tree so all deps (including tsx) resolve locally
        node_modules_source = temp_dir / "node_modules"
        node_modules_target = INSTALL_DIR / "node_modules"
        shutil.copytree(
            node_modules_source,
            node_modules_target,
            dirs_exist_ok=True,
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    gateway_script = INSTALL_DIR / "src" / "gateway" / "server.ts"
    if not gateway_script.exists():
        print(f"ERROR: Gateway script not found at {gateway_script}")
        return 1

    tsx_path = INSTALL_DIR / "node_modules" / ".bin" / "tsx"
    if sys.platform == "win32":
        tsx_path = INSTALL_DIR / "node_modules" / ".bin" / "tsx.cmd"
    if not tsx_path.exists():
        print(f"WARNING: tsx not found at {tsx_path}; startup may fail.")

    print(f"\nGateway installed at: {INSTALL_DIR}")
    print(f"Gateway script: {gateway_script}")
    print("\nNext steps:")
    print("1. Copy .env.example to .env and fill in your LLM API key.")
    print("2. Run: python start-gateway.py")
    print("3. Verify: curl http://127.0.0.1:8420/health")
    return 0


if __name__ == "__main__":
    sys.exit(main())
