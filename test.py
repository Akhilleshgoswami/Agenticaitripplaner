import asyncio

from mcp_test import (
    get_all_tools,
    get_forecast_mcp_sync,
    get_weather_mcp_sync,
    weather_mcp_call,
)


async def main():
    print("=== 1. Checking All MCP Tools ===")
    tools = await get_all_tools()
    print(f"\nTotal MCP Tools Loaded: {len(tools)}")

    print("\n=== 2. Testing Custom Weather MCP (Async) ===")
    weather_res = await weather_mcp_call("get_current_weather", {"city": "Tokyo"})
    print("Direct MCP get_current_weather(Tokyo):", weather_res)

    print("\n=== 3. Testing Weather Sync Helper ===")
    sync_weather = get_weather_mcp_sync("Paris")
    print(sync_weather)

    print("\n=== 4. Testing Forecast Sync Helper ===")
    sync_forecast = get_forecast_mcp_sync("Paris")
    print(sync_forecast)


if __name__ == "__main__":
    asyncio.run(main())
