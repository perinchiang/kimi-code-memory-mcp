#!/usr/bin/env python3
"""
TencentDB Agent Memory MCP Bridge for Kimi Code CLI.

Exposes the TencentDB Agent Memory Gateway (port 8420) as MCP tools:
- tencentdb_memory_recall: inject relevant long-term memory into context
- tencentdb_memory_capture: store a completed user/assistant turn
- tencentdb_memory_search: search L1 structured memories
- tencentdb_conversation_search: search L0 raw conversations
- tencentdb_session_end: flush pending pipeline work for a session

The Gateway must be running separately (see start-gateway.py).
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

SCRIPT_DIR = Path(__file__).parent.resolve()
load_dotenv(SCRIPT_DIR / ".env")

GATEWAY_HOST = os.getenv("TENCENTDB_GATEWAY_HOST", "127.0.0.1")
GATEWAY_PORT = int(os.getenv("TENCENTDB_GATEWAY_PORT", "8420"))
GATEWAY_API_KEY = os.getenv("TENCENTDB_GATEWAY_API_KEY", "")
GATEWAY_BASE = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}"

mcp = FastMCP("tencentdb-memory")


def _gateway_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if GATEWAY_API_KEY:
        headers["Authorization"] = f"Bearer {GATEWAY_API_KEY}"
    return headers


def _post(path: str, payload: dict) -> dict:
    url = f"{GATEWAY_BASE}{path}"
    try:
        resp = requests.post(
            url,
            json=payload,
            headers=_gateway_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to TencentDB Gateway at {GATEWAY_BASE}. "
            "Is it running? Run: python start-gateway.py"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(f"Gateway request timed out: {url}") from e


@mcp.tool()
def tencentdb_memory_recall(query: str, session_key: str) -> str:
    """
    Recall relevant long-term memory (L1/L2/L3) for the current query.

    Call this at the start of a conversation or when you need context from
    past interactions. The returned text should be injected into the system
    context.
    """
    result = _post("/recall", {"query": query, "session_key": session_key})
    context = result.get("context", "")
    count = result.get("memory_count", 0)
    strategy = result.get("strategy", "unknown")

    if not context:
        return f"[tencentdb-memory] No relevant memories recalled (count={count}, strategy={strategy})."

    return (
        f"[tencentdb-memory] Recalled {count} memory item(s) "
        f"(strategy={strategy}):\n\n{context}"
    )


@mcp.tool()
def tencentdb_memory_capture(
    user_content: str, assistant_content: str, session_key: str, session_id: str = ""
) -> str:
    """
    Capture a completed user/assistant turn into the memory pipeline.

    Call this after a meaningful exchange so the memory system can extract
    L1 atoms, L2 scenes, and L3 persona updates in the background.
    """
    payload = {
        "user_content": user_content,
        "assistant_content": assistant_content,
        "session_key": session_key,
    }
    if session_id:
        payload["session_id"] = session_id

    result = _post("/capture", payload)
    l0 = result.get("l0_recorded", 0)
    scheduled = result.get("scheduler_notified", False)
    return (
        f"[tencentdb-memory] Captured turn (L0 recorded={l0}, "
        f"scheduler_notified={scheduled})."
    )


@mcp.tool()
def tencentdb_memory_search(query: str, limit: int = 5, type_: str = "", scene: str = "") -> str:
    """
    Search structured long-term memories (L1 atoms / L2 scenarios / L3 persona).

    type_ can be one of: persona, episodic, instruction. Leave empty for hybrid.
    """
    payload = {"query": query, "limit": limit}
    if type_:
        payload["type"] = type_
    if scene:
        payload["scene"] = scene

    result = _post("/search/memories", payload)
    text = result.get("results", "")
    total = result.get("total", 0)
    strategy = result.get("strategy", "unknown")

    if not text:
        return f"[tencentdb-memory] No memory search results (total={total}, strategy={strategy})."

    return (
        f"[tencentdb-memory] Memory search results "
        f"(total={total}, strategy={strategy}):\n\n{text}"
    )


@mcp.tool()
def tencentdb_conversation_search(query: str, limit: int = 5, session_key: str = "") -> str:
    """
    Search raw conversation history (L0).

    Use this when you need verbatim past exchanges rather than summarized
    memories.
    """
    payload = {"query": query, "limit": limit}
    if session_key:
        payload["session_key"] = session_key

    result = _post("/search/conversations", payload)
    text = result.get("results", "")
    total = result.get("total", 0)

    if not text:
        return f"[tencentdb-memory] No conversation search results (total={total})."

    return (
        f"[tencentdb-memory] Conversation search results (total={total}):\n\n{text}"
    )


@mcp.tool()
def tencentdb_session_end(session_key: str) -> str:
    """
    Flush pending pipeline work for a session.

    Call this when a conversation is ending to ensure all background memory
    extraction completes.
    """
    _post("/session/end", {"session_key": session_key})
    return f"[tencentdb-memory] Session '{session_key}' ended and pipeline flushed."


if __name__ == "__main__":
    mcp.run(transport="stdio")
