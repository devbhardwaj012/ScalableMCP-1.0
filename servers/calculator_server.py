"""
Calculator MCP Server - Phase 1

Teaches:
- FastMCP vs MCPServer fallback (handles both SDK v1 and v2)
- @mcp.tool() decorator turns Python function into LLM-callable tool
- Docstring = LLM prompt, Type hints = JSON Schema (critical for tool calling)
"""
try:
    # MCP SDK v1 stable path
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("Calculator")
except ImportError:
    # MCP SDK v2 renamed FastMCP -> MCPServer
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer(name="Calculator")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together. Use this for any addition or sum query."""
    return a + b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers. Use for multiplication, product, or 'times' queries."""
    return a * b

@mcp.tool()
def explain_calculation(operation: str) -> str:
    """Explain what a math operation does. Returns human readable explanation."""
    return f"The operation '{operation}' is a basic arithmetic operation."

if __name__ == "__main__":
    # Runs as stdio server: Host starts this as subprocess and talks via JSON-RPC
    mcp.run()