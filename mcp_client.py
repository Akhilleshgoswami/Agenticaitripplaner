import asyncio
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from langchain_mcp_adapters.client import MultiServerMCPClient

BASE_DIR = Path(__file__).resolve().parent
WEATHER_SERVER_SCRIPT = BASE_DIR / "custom_weather_mcp.py"

Tavily_api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
OPEN_WEATHER_API_KEY = (
    os.getenv("OPENWEATHERMAP_API_KEY") or os.getenv("OPEN_WEATHER_API_KEY") or ""
).strip()
aviation_api_key = (
    os.getenv("AVIATION_STACK_API_KEY") or os.getenv("AVIATIONSTACK_API_KEY") or ""
).strip()

# Resolve Python / Conda interpreter path for stdio MCP
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

client_config = {}

if Tavily_api_key:
    client_config["tavily"] = {
        "transport": "streamable_http",
        "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={Tavily_api_key}",
    }

if WEATHER_SERVER_SCRIPT.exists():
    client_config["weather"] = {
        "transport": "stdio",
        "command": CONDA_PYTHON_PATH,
        "args": [str(WEATHER_SERVER_SCRIPT)],
        "env": {
            "OPENWEATHERMAP_API_KEY": OPEN_WEATHER_API_KEY,
            "OPEN_WEATHER_API_KEY": OPEN_WEATHER_API_KEY,
            "PATH": os.environ.get("PATH", ""),
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
    """Retrieve all available MCP tools across configured servers."""
    try:
        return await client.get_tools()
    except Exception as e:
        print(f"Error fetching MCP tools: {e}")
        return []


async def get_tool_by_name(tool_name: str):
    """Find a specific tool by name."""
    tools = await get_all_client()
    return next((t for t in tools if t.name == tool_name), None)


def extract_destination(query: str) -> str:
    """Extract destination city or location from query string."""
    if not query:
        return "London"

    cleaned = query.strip()
    # Check for phrases like "trip to Paris", "visit Tokyo", "in Dubai"
    patterns = [
        r"\b(?:to|in|for|visit|exploring|touring|trip to)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)",
        r"\b([A-Z][a-zA-Z]+)\s+trip\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Exclude non-location words
            if candidate.lower() not in {"flight", "flights", "hotel", "hotels", "days", "budget"}:
                return candidate.title()

    words = [w.strip("?,.!;:") for w in cleaned.split() if w.strip("?,.!;:")]
    stop_words = {
        "plan", "complete", "days", "day", "trip", "tour", "tourist", "travel",
        "budget", "flights", "flight", "hotels", "hotel", "under", "lakhs",
        "lakh", "usd", "with", "from", "and", "including", "sightseeing", "give", "me"
    }
    filtered = [w for w in words if w.lower() not in stop_words and len(w) > 2]
    if filtered:
        return filtered[-1].title()

    return "Tokyo"


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


async def tavily_mcp_search(query: str) -> str:
    """Execute Tavily search using MCP or graceful fallback."""
    tool = await get_tool_by_name("tavily_search")
    if tool:
        try:
            raw = await tool.ainvoke({"query": query})
            formatted = format_mcp_results(raw)
            if formatted:
                return formatted
        except Exception as e:
            print(f"Tavily MCP call failed: {e}")

    # Fallback to local tavily tool if available
    try:
        from tools.tavily_tool import search
        return search(query)
    except Exception as exc:
        return f"Hotel/destination search info: {exc}"


async def weather_mcp_search(city: str) -> str:
    """Execute get_current_weather using custom Weather MCP server."""
    tool = await get_tool_by_name("get_current_weather")
    if tool:
        try:
            raw = await tool.ainvoke({"city": city})
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
            print(f"Weather MCP invocation failed: {e}")

    return f"Live weather data for {city} currently unavailable."


async def forecast_mcp_search(city: str) -> str:
    """Execute get_forecast using custom Weather MCP server."""
    tool = await get_tool_by_name("get_forecast")
    if tool:
        try:
            raw = await tool.ainvoke({"city": city})
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
            print(f"Forecast MCP invocation failed: {e}")

    return f"Upcoming forecast for {city} currently unavailable."


async def aviation_mcp_call(tool_name: str, tool_args: dict | None = None) -> Any:
    """Call an AviationStack MCP tool."""
    tool = await get_tool_by_name(tool_name)
    if not tool:
        return f"Aviation tool '{tool_name}' not available on current plan."
    try:
        return await tool.ainvoke(tool_args or {})
    except Exception as e:
        return f"Aviation API error: {e}"
