"""
【entity-GitHub¦canonical_name=GitHub】 MCP Server - Phase 5

Teaches:
- How to add new servers to gateway without changing host logic
- Free 【entity-GitHub¦canonical_name=GitHub】 Search API (no key, 60 req/hour, enough for demo)

API: https://api.github.com/search/repositories?q=...
"""
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("【entity-GitHub¦canonical_name=GitHub】")
except ImportError:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer(name="【entity-GitHub¦canonical_name=GitHub】")

import httpx

@mcp.tool()
async def search_github_repos(query: str, limit: int = 5) -> str:
    """
    Search GitHub repositories by keyword.
    Example: 'mcp servers', 'python agent', 'llm gateway'
    Returns top repos with stars and description. Use for GitHub discovery.
    """
    url = f"https://api.github.com/search/repositories?q={query}&per_page={limit}&sort=stars"
    async with httpx.AsyncClient() as client:
        # GitHub requires User-Agent header
        res = await client.get(url, headers={"User-Agent": "MCP-Mastery"})
        if res.status_code!= 200:
            return f"GitHub API error {res.status_code}: {res.text[:200]}"

        data = res.json()
        items = data.get("items", [])[:limit]

        if not items:
            return f"No repos found for '{query}'"

        lines = [f"Top {len(items)} GitHub repos for '{query}':"]
        for repo in items:
            lines.append(f"- {repo['full_name']} ⭐{repo['stargazers_count']}: {repo['description']} | {repo['html_url']}")

        return "\n".join(lines)

if __name__ == "__main__":
    mcp.run()