"""
MCP Smart Host - Phase 4: Gateway Architecture

Difference vs multi_host.py (Phase 3 naive):

Naive: Connect 3 servers -> send ALL 6 tools to Groq every time
Smart: Connect 3 servers -> Router picks 1-2 relevant servers -> send only 3-4 tools

At 1000 tools: Naive = 250k tokens crash. Smart = 500 tokens constant.

Flow:
1. Connect to all servers (same as before)
2. Build router index from tool descriptions
3. For each user query: router.route(query) -> filter tools -> call Groq with FILTERED tools
4. Agentic loop (same as before) to handle multi-step tool calls
"""

import asyncio
import os
import sys
import json
import warnings
warnings.filterwarnings("ignore")

from contextlib import AsyncExitStack
from dotenv import load_dotenv
from groq import Groq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from router import MCPRouter # Our smart router from above

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SERVER_SCRIPTS = [
    "servers/calculator_server.py",
    "servers/time_server.py",
    "servers/weather_server.py",
    "servers/github_server.py",
    "servers/hackernews_server.py"
]

async def main():
    async with AsyncExitStack() as stack:
        tool_to_session = {}
        all_tools_by_server = {} # script -> [groq_tool,...]
        all_groq_tools = []
        servers_info_for_router = []

        # --- Step 1: Connect to ALL servers (like before) ---
        for script in SERVER_SCRIPTS:
            print(f"Connecting to {script}...")
            params = StdioServerParameters(command=sys.executable, args=[script], env=None)
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            tools = await session.list_tools()
            print(f" -> {len(tools.tools)} tools")

            servers_info_for_router.append({"script": script, "tools": tools.tools})

            server_groq_tools = []
            for tool in tools.tools:
                tool_to_session[tool.name] = session
                groq_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                }
                server_groq_tools.append(groq_tool)
                all_groq_tools.append(groq_tool)

            all_tools_by_server[script] = server_groq_tools

        # --- Step 2: Build Router Index (NEW) ---
        # This happens once at startup, not per query
        router = MCPRouter()
        router.index_servers(servers_info_for_router)

        print(f"\n=== GATEWAY READY ===")
        print(f"Naive would send: {len(all_groq_tools)} tools ~{len(all_groq_tools)*250} tokens every time")
        print(f"Smart Gateway sends: 1-2 servers ~250-500 tokens (constant!)")
        print(f"=====================\n")

        messages = [{"role": "system", "content": "You have tools. Use them step by step."}]

        while True:
            q = input("\nYou: ")
            if q.lower() in ["exit", "quit"]:
                break
            messages.append({"role": "user", "content": q})

            # --- Step 3: Route - Only send relevant servers (THE FIX) ---
            selected_scripts, _ = router.route(q, top_k=2)

            # Filter tools to only selected servers
            filtered_tools = []
            for script in selected_scripts:
                filtered_tools.extend(all_tools_by_server[script])

            print(f"[Gateway] Sending {len(filtered_tools)} tools to LLM, not {len(all_groq_tools)} (saved {len(all_groq_tools)-len(filtered_tools)} tools)")

            # --- Step 4: Agentic Loop with FILTERED tools ---
            # We loop because LLM might need 2 tools in sequence
            for _ in range(6):
                response = groq_client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=filtered_tools, # <-- Only relevant tools, not all
                    tool_choice="auto"
                )
                msg = response.choices[0].message

                assistant_msg = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    assistant_msg["tool_calls"] = [
                        {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls
                    ]
                messages.append(assistant_msg)

                if not msg.tool_calls:
                    print(f"\nAssistant: {msg.content}")
                    break

                for tc in msg.tool_calls:
                    print(f"-> Calling {tc.function.name} {tc.function.arguments}")
                    session = tool_to_session.get(tc.function.name)
                    args = json.loads(tc.function.arguments)
                    result = await session.call_tool(tc.function.name, arguments=args)
                    output = result.content[0].text
                    print(f"-> Returned: {output}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": output
                    })

if __name__ == "__main__":
    asyncio.run(main())