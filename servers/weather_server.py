"""
Weather MCP Server - Phase 2

Teaches:
- Calling external free APIs from inside MCP server
- Two-step API: Geocode city -> lat/lon -> weather
- Async tools: MCP supports async def for I/O bound work (httpx)

APIs used (no key needed):
- https://geocoding-api.open-meteo.com/v1/search
- https://api.open-meteo.com/v1/forecast
"""
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("Weather")
except ImportError:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer(name="Weather")

import httpx

@mcp.tool()
async def get_weather(city: str) -> str:
    """
    Get current weather for any city in the world.
    Example: 'Delhi', 'London', 'Kanpur'
    Uses live data from Open-Meteo (free, no API key).
    """
    async with httpx.AsyncClient() as client:
        # Step 1: City name -> latitude/longitude
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        geo_res = await client.get(geo_url)
        geo_data = geo_res.json()

        if not geo_data.get("results"):
            return f"Could not find city: {city}"

        loc = geo_data["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        name, country = loc["name"], loc.get("country", "")

        # Step 2: lat/lon -> weather
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,weather_code&timezone=auto"
        weather_res = await client.get(weather_url)
        current = weather_res.json()["current"]

        return f"Weather in {name}, {country}: {current['temperature_2m']}°C, Wind {current['wind_speed_10m']} km/h, Time {current['time']}"

if __name__ == "__main__":
    mcp.run()