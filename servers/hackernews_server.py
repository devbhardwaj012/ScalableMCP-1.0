"""
Hacker News MCP Server - Phase 5

Teaches: Free HN Algolia API, great for tech trends
API: https://hn.algolia.com/api/v1/search?query=...
No key, unlimited for demo.
"""
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("HackerNews")
except ImportError:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer(name="HackerNews")

import httpx

@mcp.tool()
async def search_hackernews(query: str, limit: int = 5) -> str:
    """
    Search Hacker News posts by keyword.
    Example: 'MCP', 'AI agents', 'Groq'
    Returns recent HN discussions. Use for tech news/trends.
    """
    url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage={limit}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        if res.status_code!= 200:
            return f"HN API error {res.status_code}"

        hits = res.json().get("hits", [])[:limit]
        if not hits:
            return f"No HN posts for '{query}'"

        lines = [f"Top {len(hits)} Hacker News posts for '{query}':"]
        for h in hits:
            lines.append(f"- {h['title']} ({h.get('points',0)} pts) | {h.get('url','')} | https://news.ycombinator.com/item?id={h['objectID']}")

        return "\n".join(lines)

if __name__ == "__main__":
    mcp.run()