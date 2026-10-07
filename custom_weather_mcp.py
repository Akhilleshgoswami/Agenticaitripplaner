from mcp.server.fastmcp import FastMCP
import os
import requests
from dotenv import load_dotenv

load_dotenv()
#this a custom mcp server that we can use to get weather data for a given city
mcp = FastMCP("Weather MCP")
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")

#this is a custom tool that we can use to get weather data for a given city by using the openweathermap api
# we also expose this to public by using the @mcp.tool() decorator
# we can also host it to cloud 
@mcp.tool()
def get_current_weather(city: str):
    """Ask OpenWeather for the current conditions of a city."""
    response = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={
            "q": city,
            "appid": OPENWEATHERMAP_API_KEY,
            "units": "metric",
        },
    )

    data = response.json()

    if response.status_code != 200:
        return data

    return {
        "city": data["name"],
        "temperature_c": data["main"]["temp"],
        "feels_like_c": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "condition": data["weather"][0]["description"],
        "wind_speed": data["wind"]["speed"],
    }

#this is a custom tool that we can use to get the next five forecast entries for a city by using the openweathermap api
# we also expose this to public by using the @mcp.tool() decorator
# we can also host it to cloud  
@mcp.tool()
def get_forecast(city: str):
    """Ask OpenWeather for the next five forecast time slots of a city."""
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": city,
        "appid": OPENWEATHERMAP_API_KEY,
        "units": "metric",
    }
    response = requests.get(
        url,
        params=params,
    )

    data = response.json()

    if response.status_code != 200:
        return data

    forecast = []

    # Return first 5 forecast entries
    for item in data["list"][:5]:
        forecast.append(
            {
                "datetime": item["dt_txt"],
                "temperature": item["main"]["temp"],
                "weather": item["weather"][0]["description"],
            }
        )

    return {
        "city": city,
        "forecast": forecast,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")

