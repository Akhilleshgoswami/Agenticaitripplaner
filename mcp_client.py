
import ast
import os
import asyncio
import json
import certifi
from datetime import datetime
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
llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=GROQ_API_KEY,
    temperature=0,
    max_tokens=200,
)
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
    """Print every tool from every MCP server. Used to check connections."""
    tools = await client.get_tools()
    print("available tools:")
    for tool in tools:
        print(f"- {tool.name}")
    return tools


search_tool = None
aviation_tools = None


async def initialize_mcp():
    """Load the Tavily search tool and the aviation tools once."""
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
    """Search the web through the Tavily MCP server."""
    await initialize_mcp()

    if search_tool is None:
        raise ValueError("Tavily search tool not found")

    result = await search_tool.ainvoke({"query": query})
    return format_hotel_notes(result)


async def aviation_mcp_search(query: str) -> str:
    """Call the aviation airports tool with a text query."""
    await initialize_mcp()

    if aviation_tools is None:
        raise ValueError("Aviation tools not found")

    result = await aviation_tools["airports"].invoke(query)
    return result


async def aviation_mcp_call(
    tool_name: str,
    tool_args: dict = None,
):
    """Call one AviationStack tool by name, such as list_airports."""
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
    """Start only the local weather server and keep its two tools."""
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
    """Return current weather for a city from the local weather MCP server."""
    await initialize_weather_tools()

    result = await weather_tool.ainvoke(
        {
            "city": city
        }
    )

    return unwrap_tool_payload(result)


async def forecast_mcp_search(city: str):
    """Return the next five forecast slots for a city."""
    await initialize_weather_tools()

    result = await forecast_tool.ainvoke(
        {
            "city": city
        }
    )

    return unwrap_tool_payload(result)


# ==========================================
# Tool result formatting
# ==========================================

def _loads_loose(text: str):
    """Parse JSON or a Python literal. Return None when the text is prose."""
    stripped = text.strip()
    if not stripped:
        return None

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    if stripped[0] not in "[{":
        return None

    try:
        return ast.literal_eval(stripped)
    except (ValueError, SyntaxError):
        return None


def unwrap_tool_payload(value):
    """Drop MCP content-block wrappers and return the tool's own data."""
    if isinstance(value, list):
        if not value:
            return ""
        unwrapped = [unwrap_tool_payload(item) for item in value]
        if len(unwrapped) == 1:
            return unwrapped[0]
        return unwrapped

    if isinstance(value, dict):
        is_weather = "temperature_c" in value or "forecast" in value
        is_search = "results" in value
        if not is_weather and not is_search and "text" in value:
            return unwrap_tool_payload(value.get("text"))
        return value

    if isinstance(value, str):
        parsed = _loads_loose(value)
        if parsed is None:
            return value.strip()
        return unwrap_tool_payload(parsed)

    text = getattr(value, "text", None)
    if text:
        return unwrap_tool_payload(text)

    return str(value).strip()


def _temperature(value) -> str:
    """Show a Celsius reading with one decimal."""
    number = float(value)
    return f"{number:.1f}"


def _forecast_time(value) -> str:
    """Turn an OpenWeather timestamp into a short label."""
    try:
        moment = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return str(value)
    return moment.strftime("%a %d %b, %H:%M")


def _weather_lines(current, forecast) -> str:
    """Build the weather panel from current conditions and forecast slots."""
    lines = []

    if isinstance(current, dict) and "temperature_c" in current:
        city = current.get("city") or "Destination"
        condition = str(current.get("condition") or "").strip()
        summary = f"{city}: {_temperature(current['temperature_c'])}°C"
        if condition:
            summary = f"{summary}, {condition}"
        lines.append(summary)
        if current.get("feels_like_c") is not None:
            lines.append(f"Feels like {_temperature(current['feels_like_c'])}°C")
        if current.get("humidity") is not None:
            lines.append(f"Humidity {current['humidity']}%")
        if current.get("wind_speed") is not None:
            lines.append(f"Wind {_temperature(current['wind_speed'])} m/s")
    elif isinstance(current, dict) and current.get("message"):
        lines.append(f"Current weather is unavailable: {current['message']}")
    elif isinstance(current, str) and current.strip():
        lines.append(current.strip())

    slots = forecast.get("forecast") if isinstance(forecast, dict) else None
    if isinstance(slots, list) and slots:
        lines.append("")
        lines.append("Forecast")
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            when = _forecast_time(slot.get("datetime", ""))
            weather = slot.get("weather") or ""
            if slot.get("temperature") is None:
                lines.append(f"{when} · {weather}".strip(" ·"))
                continue
            lines.append(
                f"{when} · {_temperature(slot['temperature'])}°C · {weather}".strip(" ·")
            )
    elif isinstance(forecast, dict) and forecast.get("message"):
        lines.extend(["", f"Forecast is unavailable: {forecast['message']}"])
    elif isinstance(forecast, str) and forecast.strip():
        lines.extend(["", forecast.strip()])

    return "\n".join(lines).strip()


def format_weather_report(current, forecast=None) -> str:
    """Turn raw weather tool output into a short readable report."""
    if (
        forecast is None
        and isinstance(current, str)
        and "temperature_c" not in current
        and "[{'type':" not in current
    ):
        return current.strip()

    if forecast is None and isinstance(current, str) and "Forecast:" in current:
        current_text, forecast_text = current.split("Forecast:", 1)
        current_text = current_text.replace("Current Weather:", "", 1).strip()
        return _weather_lines(
            unwrap_tool_payload(current_text),
            unwrap_tool_payload(forecast_text),
        )

    return _weather_lines(
        unwrap_tool_payload(current),
        unwrap_tool_payload(forecast) if forecast is not None else None,
    )


def format_hotel_notes(result) -> str:
    """Turn a Tavily hotel search into a short list of places."""
    payload = unwrap_tool_payload(result)
    if isinstance(payload, str):
        return payload.strip()

    results = []
    summary = ""
    if isinstance(payload, dict):
        summary = str(payload.get("answer") or "").strip()
        results = payload.get("results") or []
    elif isinstance(payload, list):
        results = payload

    lines = []
    if summary and summary.lower() != "none":
        lines.extend([summary, ""])

    notes = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
        content = " ".join(str(item.get("content") or item.get("snippet") or "").split())
        if len(content) > 220:
            content = content[:217].rstrip() + "..."
        url = str(item.get("url") or "").strip()
        note = [title]
        if content:
            note.append(content)
        if url:
            note.append(url)
        notes.append("\n".join(note))
        if len(notes) == 5:
            break

    if notes:
        lines.append("\n\n".join(notes))

    formatted = "\n".join(lines).strip()
    if formatted:
        return formatted

    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return ""


# ==========================================
# Destination extractor
# ==========================================

def extract_destination(query: str):
    """Ask Groq for only the destination city or country named in the request."""
    prompt = f"""
    Extract only the destination city or country.

    Query:
    {query}

    Return only destination name.
    """

    response = llm.invoke(prompt)

    return response.content.strip()