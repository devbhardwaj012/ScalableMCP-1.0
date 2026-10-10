import asyncio
import os
import sys
import json
import warnings
warnings.filterwarnings("ignore") # hides that lifespan warning

from dotenv import load_dotenv
from groq import Groq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
# This model is 100% available on free Groq
MODEL = "openai/gpt-oss-120b"

async def main():
    server_params = StdioServerParameters(
        command=sys.executable, # uses your.venv python
        args=["servers/calculator_server.py"],
        env=None
    )

    print("Starting MCP server...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            print(f"Connected! Found tools: {[t.name for t in tools_response.tools]}")

            groq_tools = []
            for tool in tools_response.tools:
                groq_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })

            messages = [{"role": "system", "content": "You are a helpful assistant with calculator tools. Use them when needed."}]

            while True:
                user_input = input("\nYou: ")
                if user_input.lower() in ["exit", "quit"]:
                    break

                messages.append({"role": "user", "content": user_input})

                try:
                    response = groq_client.chat.completions.create(
                        model=MODEL,
                        messages=messages,
                        tools=groq_tools,
                        tool_choice="auto"
                    )
                except Exception as e:
                    print(f"Groq Error: {e}")
                    print("Tip: Check your.env has GROQ_API_KEY")
                    continue

                response_message = response.choices[0].message
                # Important: convert to dict format for history
                messages.append({
                    "role": "assistant",
                    "content": response_message.content,
                    "tool_calls": [
                        {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in (response_message.tool_calls or [])
                    ] if response_message.tool_calls else None
                })

                if response_message.tool_calls:
                    for tool_call in response_message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        print(f"-> LLM wants to call {tool_name}({tool_args})")

                        result = await session.call_tool(tool_name, arguments=tool_args)
                        tool_output = result.content[0].text
                        print(f"-> Tool returned: {tool_output}")

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_output
                        })

                    final_response = groq_client.chat.completions.create(
                        model=MODEL,
                        messages=messages
                    )
                    final_answer = final_response.choices[0].message.content
                    print(f"\nAssistant: {final_answer}")
                    messages.append({"role": "assistant", "content": final_answer})
                else:
                    print(f"\nAssistant: {response_message.content}")

if __name__ == "__main__":
    asyncio.run(main())