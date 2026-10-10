# MCP Mastery - Scalable Gateway for 1000+ Tools

> A production-grade MCP architecture that solves the 1000-tools bottleneck with semantic routing.
> Built using Python 3.13, Groq (free), no API keys for tools.

## The Problem This Solves

**Naive MCP Host:**
```
User Query -> Send 1000 tool definitions (250,000 tokens) -> LLM -> Slow, expensive, crashes
```

**Smart Gateway (this project):**
```
User Query -> Embed query -> Semantic search -> Pick Top 2 servers -> Send 2-4 tools (500 tokens) -> LLM
```
Constant token cost, scales to thousands of MCP servers.

This is the exact bottleneck when you have 100+ MCPs.

---

## What is MCP?

**MCP = USB-C for AI**

- **MCP Server:** Exposes capabilities. Has Tools (functions LLM can CALL), Resources (data LLM can READ), Prompts (templates).
- **MCP Client:** Bridge inside your app that starts server process via stdio and speaks JSON-RPC.
- **MCP Host:** Your app + LLM. Owns clients, decides which tool to call, executes it.

Transport:
- `stdio` = local subprocess `python3 server.py` (we start here)
- `Streamable HTTP` = remote service (Phase 6)

## Project Structure

```
first/
├── servers/
│   ├── calculator_server.py    # Phase 1 - Math tools
│   ├── time_server.py          # Phase 2 - Time, uses zoneinfo (no deprecated utcnow)
│   ├── weather_server.py       # Phase 2 - Real weather via Open-Meteo (no key)
│   ├── github_server.py        # Phase 5 - Search GitHub repos (free API)
│   └── hackernews_server.py    # Phase 5 - Search Hacker News (free API)
├── host/
│   ├── groq_host.py            # Phase 1 - Single server host
│   ├── multi_host.py           # Phase 3 - Naive multi-host (shows bottleneck)
│   ├── router.py               # Phase 4 - Smart Router with local embeddings
│   └── smart_host.py           # Phase 4/5 - Gateway using router
├── .env                        # GROQ_API_KEY + GROQ_MODEL
├── requirements.txt
└── README.md
```

## Setup - Phase 0

```bash
# Inside project folder
python3 -m venv .venv
source .venv/bin/activate

pip3 install "mcp==1.12.0" groq python-dotenv httpx sentence-transformers

# Get free key from https://console.groq.com/keys
touch .env
# Add to .env:
# GROQ_API_KEY=gsk_...
# GROQ_MODEL=openai/gpt-oss-120b
```

Note: `pydantic_settings` warning about `lifespan` comes from MCP SDK itself, harmless. We filter it.

## Phase 1: Your First MCP Server + Host

**Concept:** Tool docstring = LLM prompt. Type hints = JSON Schema.

```bash
python3 host/groq_host.py
# Try: what is 1234*5678
```

You learn the core loop: `User -> Groq thinks -> Host executes via Client -> Server returns -> Groq final answer`

## Phase 2: Real Servers with Free APIs

No keys needed:
- `time_server.py` uses `zoneinfo` (Python 3.9+ stdlib, no pytz, no deprecated utcnow)
- `weather_server.py` uses Open-Meteo: Geocoding API + Forecast API

Test each alone:
```bash
python3 servers/weather_server.py # should wait, no error. Ctrl+C
npx @modelcontextprotocol/inspector python3 servers/weather_server.py
```

## Phase 3: Naive Multi-Host - Where Bottleneck Appears

```bash
python3 host/multi_host.py
# Try: what is the weather in kanpur and what is 789*1234
```

Check log:
```
=== BOTTLENECK CHECK ===
Total tools: 6 | Est tokens: ~1500
If 100 servers * 10 tools = 1000 tools => ~250,000 tokens = context dies
```

At 3 servers it works. At 100 servers, it crashes. This is what you wanted to solve.

Also teaches: Agentic Loop (LLM can call tools in sequence), tool_to_session mapping.

## Phase 4: Smart Gateway - The Fix

```bash
pip3 install sentence-transformers
python3 host/smart_host.py
# First run downloads ~80MB model all-MiniLM-L6-v2 to ~/.cache, then offline

# Try:
# what is the temperature in delhi
# what is 567*567
# what is the weather in kanpur and what is 567*678
```

Logs:
```
[Router] Query: 'what is the temperature in delhi'
 - weather_server.py score: 0.302
 - time_server.py score: 0.093
[Router] Selected -> ['servers/weather_server.py', 'servers/time_server.py']
[Gateway] Sending 3 tools to LLM, not 6 (saved 3 tools)
```

**How router works:** Embeds server descriptions locally on M4, cosine similarity search, top_k=2. Constant token cost.

## Phase 5: Scale to 5+ Servers

Add free API servers:

```bash
python3 host/smart_host.py
# Try: search github for mcp servers
# Try: search hackernews about AI agents
```

Now:
- Naive would send 10+ tools ~2500 tokens
- Smart sends 2 servers ~500 tokens

## How to Add Your Own Server

1. Create `servers/my_server.py`:
```python
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("MyServer")
except ImportError:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer(name="MyServer")

@mcp.tool()
def my_tool(arg: str) -> str:
    """Clear description - LLM uses this to decide when to call it."""
    return f"Result for {arg}"

if __name__ == "__main__":
    mcp.run()
```

2. Add path to `SERVER_SCRIPTS` in `smart_host.py`
3. Router auto-indexes it.

## Tech Stack

- Python 3.13, 
- MCP SDK 1.12.0 (FastMCP)
- Groq API - `openai/gpt-oss-120b` (free, 120B, great tool calling)
- sentence-transformers `all-MiniLM-L6-v2` (local embeddings, 384 dim)
- Free APIs: Open-Meteo, GitHub Search, HN Algolia

## Future Improvements

- [ ] Replace stdio with Streamable HTTP for remote servers
- [ ] Add Qdrant for persistent vector DB
- [ ] LLM as router fallback when similarity < 0.3
- [ ] Tool result caching
- [ ] Resources + Prompts (not just Tools)



## License

MIT
