
import os
import asyncio
import certifi
from pathlib import Path
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_groq import ChatGroq
load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

WEATHER_SERVER_PATH = Path(__file__).resolve().parent / "custom_weather_mcp.py"
TRAVLE_PYTHON = Path("/Users/akhileshgoswami/anaconda3/envs/travle/bin/python")
llm = ChatGroq(model="openai/gpt-oss-120b",api_key=GROQ_API_KEY)
client = MultiServerMCPClient(
    # MCP servers to use
       {
        "tavily": {
            "transport":"streamable_http",
            "url":f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}"
        },
    "aviationstack": {
      "transport":"stdio", # for local sever we use stdio, for remote server we use streamable_http
      "command": "uvx",
      "args": [
        "aviationstack-mcp"
      ],
      "env": {
        "AVIATION_STACK_API_KEY": AVIATIONSTACK_API_KEY
      }
    },
    "weather": {
      "transport": "stdio", # we use stdio to run the custom weather mcp server locally
      "command": str(TRAVLE_PYTHON), # path to the python interpreter
      "args": [
        str(WEATHER_SERVER_PATH) # path to the custom weather mcp server
      ],
      "env": {
        "OPENWEATHERMAP_API_KEY": OPENWEATHERMAP_API_KEY # environment variable for the openweathermap api key
      }
    }
       }
)

# Check if the client is connected to all servers
async def get_all_tools():
    tools = await client.get_tools()
    print("available tools:")
    for tool in tools:
        print(f"- {tool.name}")
    return tools


search_tool = None
aviation_tools = None


async def initialize_mcp():
    global search_tool
    global aviation_tools

    if search_tool is not None and aviation_tools:
        return

    tools = await client.get_tools()

    print("\nAvailable MCP Tools:\n")
    for tool in tools:
        print(tool.name)

    search_tool = next(
        tool for tool in tools if tool.name == "tavily_search"
    )

    aviation_tools = {
        tool.name: tool
        for tool in tools
        if tool.name != "tavily_search"
    }


async def tavily_mcp_search(query: str) -> str:
     await initialize_mcp()

     if search_tool is None:
        raise ValueError("Tavily search tool not found")

     result = await search_tool.ainvoke({"query": query})
     return result


async def aviation_mcp_search(query: str) -> str:
     await initialize_mcp()

     if aviation_tools is None:
        raise ValueError("Aviation tools not found")

     result = await aviation_tools["airports"].invoke(query)
     return result


async def aviation_mcp_call(
    tool_name: str,
    tool_args: dict = None,
):
    tools = await client.get_tools()

    tool = next(
        t for t in tools
        if t.name == tool_name
    )

    result = await tool.ainvoke(
        tool_args or {}
    )
    return result

# ==========================================
# Weather MCP tools
# ==========================================

weather_tool = None
forecast_tool = None


async def initialize_weather_tools():
    global weather_tool
    global forecast_tool

    if (
        weather_tool is not None
        and forecast_tool is not None
    ):
        return

    if not WEATHER_SERVER_PATH.exists():
        raise FileNotFoundError(
            "Weather MCP server file was not found: "
            f"{WEATHER_SERVER_PATH}"
        )

    # Load only Weather.
    # Tavily and AviationStack will not be started.
    tools = await client.get_tools(
        server_name="weather"
    )

    tools_by_name = {
        tool.name: tool
        for tool in tools
    }

    weather_tool = tools_by_name.get(
        "get_current_weather"
    )

    forecast_tool = tools_by_name.get(
        "get_forecast"
    )

    missing_tools = []

    if weather_tool is None:
        missing_tools.append(
            "get_current_weather"
        )

    if forecast_tool is None:
        missing_tools.append(
            "get_forecast"
        )

    if missing_tools:
        available_tools = ", ".join(
            tools_by_name.keys()
        )

        raise RuntimeError(
            "Missing Weather MCP tools: "
            f"{', '.join(missing_tools)}. "
            f"Available tools: "
            f"{available_tools or 'none'}"
        )


async def weather_mcp_search(city: str):
    await initialize_weather_tools()

    result = await weather_tool.ainvoke(
        {
            "city": city
        }
    )

    return result


async def forecast_mcp_search(city: str):
    await initialize_weather_tools()

    result = await forecast_tool.ainvoke(
        {
            "city": city
        }
    )

    return result


# ==========================================
# Destination extractor
# ==========================================

def extract_destination(query: str):
    prompt = f"""
    Extract only the destination city or country.

    Query:
    {query}

    Return only destination name.
    """

    response = llm.invoke(prompt)

    return response.content.strip()