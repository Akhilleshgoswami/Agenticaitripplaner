import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

from tools import tavily_tool

load_dotenv()

from langchain_mcp_adapters.client import MultiServerMCPClient

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
WEATHER_SERVER_SCRIPT = BASE_DIR / "custom_weather_mcp.py"

Tavily_api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
OPEN_WEATHER_API_KEY = (
    os.getenv("OPENWEATHERMAP_API_KEY") or os.getenv("OPEN_WEATHER_API_KEY") or ""
).strip()
aviation_api_key = (
    os.getenv("AVIATION_STACK_API_KEY") or os.getenv("AVIATIONSTACK_API_KEY") or ""
).strip()

# Resolve Conda / Python path for stdio MCP servers
CONDA_PYTHON_PATH = (
    os.getenv("CONDA_PYTHON_PATH")
    or (
        os.path.join(os.environ["CONDA_PREFIX"], "bin", "python")
        if "CONDA_PREFIX" in os.environ
        else None
    )
    or (
        "/Users/akhileshgoswami/anaconda3/envs/tripplaner/bin/python"
        if os.path.exists("/Users/akhileshgoswami/anaconda3/envs/tripplaner/bin/python")
        else None
    )
    or (
        "/Users/akhileshgoswami/anaconda3/bin/python"
        if os.path.exists("/Users/akhileshgoswami/anaconda3/bin/python")
        else None
    )
    or sys.executable
)

client_config = {
    "tavily": {
        "transport": "streamable_http",
        "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={Tavily_api_key}",
    },
    # Custom Weather MCP Server running via stdio with Conda Python environment
    "weather": {
        "transport": "stdio",
        "command": CONDA_PYTHON_PATH,
        "args": [str(WEATHER_SERVER_SCRIPT)],
        "env": {
            "OPENWEATHERMAP_API_KEY": OPEN_WEATHER_API_KEY,
            "OPEN_WEATHER_API_KEY": OPEN_WEATHER_API_KEY,
            "PATH": os.environ.get("PATH", ""),
        },
    },
}

if aviation_api_key:
    client_config["aviationstack"] = {
        "transport": "stdio",
        "command": "uvx",
        "args": ["aviationstack-mcp"],
        "env": {"AVIATION_STACK_API_KEY": aviation_api_key},
    }

client = MultiServerMCPClient(client_config)


async def get_all_client():
    return await client.get_tools()


tavily_search_tool = None


async def get_tavily_search_tool():
    global tavily_search_tool

    if tavily_search_tool is not None:
        return tavily_search_tool

    tools = await get_all_client()

    tavily_search_tool = next(
        (tool for tool in tools if tool.name == "tavily_search"), None
    )
    return tavily_search_tool


def format_mcp_results(raw_response) -> str:
    """Format raw MCP output into markdown text."""
    try:
        if isinstance(raw_response, list) and len(raw_response) > 0:
            first = raw_response[0]
            if isinstance(first, dict) and "text" in first:
                data = json.loads(first["text"])
                results = data.get("results", [])
                formatted = []
                for i, r in enumerate(results, 1):
                    title = r.get("title", "Unknown")
                    url = r.get("url", "")
                    content = r.get("content", "").strip()
                    if len(content) > 300:
                        content = content[:300].rsplit(" ", 1)[0] + "..."
                    formatted.append(f"{i}. **{title}**\n   {url}\n   {content}")
                if formatted:
                    return "\n\n".join(formatted)
        elif isinstance(raw_response, str):
            return raw_response
    except Exception as e:
        print("Error formatting MCP response:", e)

    return str(raw_response) if raw_response else ""


def search_hotels_mcp_sync(query: str) -> str:
    """Synchronously execute Tavily MCP search safe for sync/async contexts."""
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            raw = executor.submit(
                lambda: asyncio.run(get_tavily_mcp_search(query))
            ).result(timeout=15)
        formatted = format_mcp_results(raw)
        if formatted:
            return formatted
    except Exception as e:
        print(f"MCP search encountered an issue: {e}. Falling back to standard search.")

    # Graceful fallback to standard Tavily client
    try:
        from tools.tavily_tool import search

        return search(query)
    except Exception as e:
        return f"Unable to fetch hotel results: {e}"


async def get_all_tools():
    tools = await get_all_client()
    for tool in tools:
        print(tool.name)
    return tools


aviation_tools = None
tavily_tools = {}


async def initmcp():

    global aviation_tools, tavily_tools
    all_tools = await get_all_tools()
    tavily_tool = next(tool for tool in all_tools if tool.name == "tavily_search")
    aviation_tools = next(tool for tool in all_tools if tool.name != "tavily_search")


async def get_tavily_mcp_search(query: str):
    tool = await get_tavily_search_tool()
    if tool is None:
        return None
    return await tool.ainvoke({"query": query})


async def aviation_mcp_call(tool_name: str, tool_args: dict | None = None):
    tools = await get_all_client()
    tool = next((tool for tool in tools if tool.name == tool_name), None)
    if not tool:
        raise ValueError(f"Tool '{tool_name}' not found among MCP tools.")
    return await tool.ainvoke(tool_args or {})


async def weather_mcp_call(tool_name: str, tool_args: dict | None = None):
    """Invoke a tool provided by the custom Weather MCP server."""
    tools = await get_all_client()
    tool = next((tool for tool in tools if tool.name == tool_name), None)
    if not tool:
        raise ValueError(
            f"Weather tool '{tool_name}' not found. Available: {[t.name for t in tools]}"
        )
    return await tool.ainvoke(tool_args or {})


def get_weather_mcp_sync(city: str) -> str:
    """Fetch current weather for a city using custom Weather MCP server (safe for sync calls)."""
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            raw = executor.submit(
                lambda: asyncio.run(weather_mcp_call("get_current_weather", {"city": city}))
            ).result(timeout=15)

        if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], dict) and "text" in raw[0]:
            try:
                data = json.loads(raw[0]["text"])
                if isinstance(data, dict):
                    if "error" in data:
                        return f"Weather info: {data['error']}"
                    temp = data.get("temperature_c", "N/A")
                    feels = data.get("feels_like_c", "N/A")
                    desc = data.get("description", "N/A")
                    humidity = data.get("humidity", "N/A")
                    wind = data.get("wind_speed", "N/A")
                    c_name = data.get("city", city)
                    return f"**{c_name} Weather**: {desc.title()}, {temp}°C (Feels like: {feels}°C, Humidity: {humidity}%, Wind: {wind} m/s)"
            except Exception:
                return str(raw[0]["text"])
        return str(raw) if raw else ""
    except Exception as e:
        print(f"Weather MCP call failed: {e}")
        return f"Weather information unavailable: {e}"


def get_forecast_mcp_sync(city: str) -> str:
    """Fetch 3-hour forecasts for a city using custom Weather MCP server (safe for sync calls)."""
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            raw = executor.submit(
                lambda: asyncio.run(weather_mcp_call("get_forecast", {"city": city}))
            ).result(timeout=15)

        if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], dict) and "text" in raw[0]:
            try:
                data = json.loads(raw[0]["text"])
                if isinstance(data, dict):
                    forecast_list = data.get("forecast", [])
                    c_name = data.get("city", city)
                    lines = [f"**{c_name} Upcoming Forecast**:"]
                    for f in forecast_list:
                        dt = f.get("datetime", "")
                        temp = f.get("temperature_c", "")
                        cond = f.get("condition", "")
                        lines.append(f"- {dt}: {temp}°C, {cond}")
                    return "\n".join(lines)
            except Exception:
                return str(raw[0]["text"])
        return str(raw) if raw else ""
    except Exception as e:
        print(f"Weather forecast MCP call failed: {e}")
        return f"Weather forecast unavailable: {e}"
