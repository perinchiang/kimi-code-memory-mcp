# kimi-code-memory-mcp

A Python MCP (Model Context Protocol) bridge that exposes [TencentDB Agent Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) as MCP tools for [Kimi Code](https://kimi.com) CLI.

## What it does

Gives your AI coding assistant **long-term memory** across sessions:

- **L0** - Raw conversation storage
- **L1** - Atomic memory facts (auto-extracted)
- **L2** - Scene/context blocks (auto-clustered)
- **L3** - User persona/profile (auto-generated)

The LLM can recall relevant memories, capture new conversations, and search past interactions.

## Architecture

```
Kimi Code CLI  <---stdio--->  Python MCP Bridge (this repo)
                                   |
                                   | HTTP :8420
                                   v
                          TencentDB Agent Memory Gateway
                          (official npm package, runs locally)
```

This repo is a **thin Python bridge** — it forwards 5 MCP tools to the official Gateway via HTTP. The Gateway does all the heavy lifting (L0-L3 extraction, vector search, persona generation).

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up the Gateway (one-time)

```bash
python setup-gateway.py
```

This installs the official `@tencentdb-agent-memory/memory-tencentdb` npm package and `tsx` into `~/.memory-tencentdb/`.

### 3. Configure credentials

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

You need:
- **LLM API key** — any OpenAI-compatible endpoint (SiliconFlow, OpenAI, SenseNova, etc.)
- **SiliconFlow API key** — for embeddings (BAAI/bge-m3)

### 4. Start the Gateway

```bash
python start-gateway.py
```

For background/autostart mode:
```bash
python start-gateway-background.py
```

### 5. Register in Kimi Code

Add to your `~/.kimi-code/mcp.json`:

```json
{
  "mcpServers": {
    "tencentdb-memory": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}
```

### 6. (Optional) Auto-invoke on every conversation with `AGENTS.md`

If you want Kimi Code to **automatically** recall memories at the start of every conversation and capture them after each turn, create an `AGENTS.md` file in your project root. `AGENTS.md` is a project-scope instruction file that Kimi Code loads automatically; it is **not** a skill and does not require a trigger word.

Example `AGENTS.md`:

```markdown
# TencentDB Agent Memory Rules

- **Fixed session_key:** always use `kimi-default` (or any stable identifier).
- **On the first user message of every conversation:**
  - Call `mcp__tencentdb-memory__tencentdb_memory_recall` with `session_key="kimi-default"`.
  - Do not answer the user until this recall has been attempted.
- **After every meaningful user/assistant turn:**
  - Call `mcp__tencentdb-memory__tencentdb_memory_capture` with `user_content`, `assistant_content`, and `session_key="kimi-default"`.
- **When the session ends:**
  - Call `mcp__tencentdb-memory__tencentdb_session_end` with `session_key="kimi-default"`.
```

This is useful for keeping a single, persistent memory context across all your chats in a workspace.

## MCP Tools

| Tool | Description |
|------|-------------|
| `tencentdb_memory_recall` | Recall relevant L1/L2/L3 memories for current query |
| `tencentdb_memory_capture` | Store a completed conversation turn into memory pipeline |
| `tencentdb_memory_search` | Search structured memories (L1-L3) with optional type filter |
| `tencentdb_conversation_search` | Search raw L0 conversation history |
| `tencentdb_session_end` | Flush pending extraction work for a session |

## SKILL.md

Include `SKILL.md` in your Kimi Code skills directory to teach the LLM when and how to use these memory tools.

## Requirements

- Python >= 3.12
- Node.js >= 22.16.0 (for the Gateway)
- An OpenAI-compatible LLM API key
- A SiliconFlow API key (for embeddings)

## Acknowledgments

- [TencentDB-Agent-Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) by TencentCloud (MIT License)
- [FastMCP](https://github.com/jlowin/fastmcp) Python framework

## License

MIT — see [LICENSE](LICENSE)

This project includes modifications based on TencentDB-Agent-Memory by TencentCloud.
