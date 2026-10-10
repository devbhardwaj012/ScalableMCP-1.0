"""
Time MCP Server - Phase 2

Teaches:
- Never use datetime.utcnow() (deprecated since Python 3.12)
- Use datetime.now(timezone.utc) for UTC, ZoneInfo for IANA timezones
- zoneinfo is stdlib on Python 3.9+, no need for pytz
"""
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("Time")
except ImportError:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer(name="Time")

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

@mcp.tool()
def get_current_time(timezone_name: str = "UTC") -> str:
    """
    Get current time in any IANA timezone.
    Example: Asia/Kolkata, America/New_York, Europe/London, UTC.
    Use for: "what time is it in Delhi" type queries.
    """
    try:
        tz = ZoneInfo(timezone_name)
        now = datetime.now(tz)
        return now.strftime(f"%Y-%m-%d %H:%M:%S %Z in {timezone_name}")
    except ZoneInfoNotFoundError:
        return f"Invalid timezone '{timezone_name}'. Use IANA format like 'Asia/Kolkata'."
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def get_utc_time() -> str:
    """Get current UTC time. Use when you need universal timestamp."""
    # Correct modern way, not datetime.utcnow()
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S UTC")

if __name__ == "__main__":
    mcp.run()