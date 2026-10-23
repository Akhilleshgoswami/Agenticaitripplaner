import os
from typing import Any

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()
mcp = FastMCP("Weather Mcp")

OPEN_API_WEATHER_KEY = (
    os.getenv("OPENWEATHERMAP_API_KEY") or os.getenv("OPEN_WEATHER_API_KEY") or ""
).strip()


@mcp.tool()
async def get_current_weather(city: str) -> dict[str, Any]:
    """Get the current weather and temperature in Celsius for a given city."""
    city = (city or "").strip()
    if not city:
        return {"error": "City name cannot be empty"}

    response = requests.get(
        f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPEN_API_WEATHER_KEY}&units=metric"
    )
    data = response.json()
    if response.status_code != 200:
        return data

    weather_desc = data["weather"][0]["description"] if data.get("weather") else "N/A"
    icon = data["weather"][0]["icon"] if data.get("weather") else ""

    return {
        "city": data.get("name", city),
        "temperature_c": data.get("main", {}).get("temp"),
        "feels_like_c": data.get("main", {}).get("feels_like"),
        "description": weather_desc,
        "icon": icon,
        "humidity": data.get("main", {}).get("humidity"),
        "wind_speed": data.get("wind", {}).get("speed"),
        "wind_direction": data.get("wind", {}).get("deg"),
        "pressure": data.get("main", {}).get("pressure"),
        "visibility": data.get("visibility"),
        "sunrise": data.get("sys", {}).get("sunrise"),
        "sunset": data.get("sys", {}).get("sunset"),
    }


@mcp.tool()
def get_forecast(city: str) -> dict[str, Any]:
    """Return the upcoming 3-hour forecast entries (in Celsius) for a city."""
    city = (city or "").strip()
    if not city:
        return {"error": "City cannot be empty"}

    response = requests.get(
        f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPEN_API_WEATHER_KEY}&units=metric"
    )
    data = response.json()
    if response.status_code != 200:
        return data

    forecast = [
        {
            "datetime": item.get("dt_txt"),
            "temperature_c": item.get("main", {}).get("temp"),
            "condition": item.get("weather", [{}])[0].get("description", ""),
        }
        for item in data.get("list", [])[:5]
    ]

    return {
        "city": data.get("city", {}).get("name", city),
        "forecast": forecast,
    }


if __name__ == "__main__":
    mcp.run()
