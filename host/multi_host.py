"""
MCP Multi-Host - Phase 3: Naive Approach

This file demonstrates the classic MCP architecture AND its bottleneck.

Concepts taught:
1. MCP Host: Your app + LLM (Groq) that decides what to do
2. MCP Client: The bridge that starts a server subprocess via stdio
3. MCP Server: Exposes tools (calculator, time, weather)
4. Agentic Loop: LLM can call tools multiple times in sequence
5. Bottleneck: Sending ALL tools to LLM every time = token explosion

This is the file you will refactor in Phase 4 into a Smart Gateway.
"""

import asyncio
import os
import sys
import json
import warnings

# This warning comes from inside the MCP SDK itself (pydantic), not your code.
# We hide it to keep logs clean. It's harmless.
warnings.filterwarnings("ignore")

from contextlib import AsyncExitStack # Manages multiple servers cleanly
from dotenv import load_dotenv
from groq import Groq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load GROQ_API_KEY from.env
load_dotenv()

# Groq client - using openai/gpt-oss-120b as you set. Fast + great tool calling.
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# List all MCP servers you want to connect. Just add a file path to scale.
# Each file is a separate process (isolated, safe).
SERVER_SCRIPTS = [
    "servers/calculator_server.py",
    "servers/time_server.py",
    "servers/weather_server.py"
]

async def main():
    # AsyncExitStack lets us open 3, 10, 100 servers and auto-close them on exit.
    # Without it, you'd leak processes.
    async with AsyncExitStack() as stack:

        # Mapping: tool_name -> session that owns it
        # Example: "get_weather" -> weather server session
        # This solves tool name collisions at scale.
        tool_to_session = {}
        all_groq_tools = []

        # --- Step 1: Connect to ALL servers and collect their tools ---
        for script in SERVER_SCRIPTS:
            print(f"Connecting to {script}...")

            # StdioServerParameters = how to start the server
            # command = sys.executable ensures we use your.venv python, not system python
            params = StdioServerParameters(
                command=sys.executable,
                args=[script],
                env=None
            )

            # stdio_client starts the server as a subprocess and gives us read/write streams
            read, write = await stack.enter_async_context(stdio_client(params))

            # ClientSession is the MCP Client that speaks JSON-RPC over those streams
            session = await stack.enter_async_context(ClientSession(read, write))

            # Handshake with server
            await session.initialize()

            # Ask server: "what tools do you have?"
            tools_response = await session.list_tools()
            print(f" -> Found {len(tools_response.tools)} tools")

            # Convert MCP tool format -> Groq/OpenAI tool format
            for tool in tools_response.tools:
                # Cache which session owns this tool
                tool_to_session[tool.name] = session

                # Groq expects: {type: "function", function: {name, description, parameters}}
                all_groq_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema # JSON Schema from Python type hints
                    }
                })

        # --- Step 2: The Bottleneck Check (Your Original Question) ---
        # This is why naive approach fails at 100+ servers
        total_tools = len(all_groq_tools)
        print(f"\n=== BOTTLENECK CHECK ===")
        print(f"Total tools loaded: {total_tools}")
        print(f"Est tokens for tool definitions: ~{total_tools * 250}")
        print(f"If 100 servers * 10 tools = 1000 tools => ~250,000 tokens!")
        print(f"LLM context dies, cost explodes, latency high.")
        print(f"Phase 4 will fix this with semantic routing.")
        print(f"========================\n")

        # --- Step 3: Chat Loop + Agentic Loop ---
        # messages = full conversation history that Groq sees
        messages = [{"role": "system", "content": "You have tools. Use them step by step when needed."}]

        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ["exit", "quit"]:
                break

            messages.append({"role": "user", "content": user_input})

            # Agentic Loop: Keep calling LLM until it stops asking for tools
            # This allows: weather + multiply in ONE user query = 2 tool calls in sequence
            for _ in range(6): # Safety: max 6 tool steps per user message
                # IMPORTANT: We send ALL tools every time - this is the bottleneck
                response = groq_client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=all_groq_tools,
                    tool_choice="auto" # Let LLM decide if it needs a tool
                )
                msg = response.choices[0].message

                # Build assistant message in Groq's required format
                # Must include tool_calls array if LLM called tools
                assistant_msg = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                messages.append(assistant_msg)

                # No more tool calls? We're done, print final answer
                if not msg.tool_calls:
                    print(f"\nAssistant: {msg.content}")
                    break

                # Execute all tool calls the LLM requested in this turn
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.function.name
                    print(f"-> Calling {tool_name} {tool_call.function.arguments}")

                    session = tool_to_session.get(tool_name)
                    if not session:
                        print(f" -> No session found for {tool_name}")
                        continue

                    # Parse arguments from JSON string -> dict
                    args = json.loads(tool_call.function.arguments)

                    # Call the MCP server tool via ClientSession
                    result = await session.call_tool(tool_name, arguments=args)
                    output = result.content[0].text
                    print(f"-> Tool returned: {output}")

                    # Tool result must have matching tool_call_id
                    # This links result to the specific tool call
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": output
                    })
                # Loop continues: LLM now sees tool results and can call next tool or answer

if __name__ == "__main__":
    asyncio.run(main())