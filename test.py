# from tools.travily_tool import travily_serach
#
# res = travily_serach("Who is prime minster of india")
# print(res)
# from tools.flight_tool import search_flights
import asyncio
# # print(search_flights("Plan a 7 days Japan trip from India"))

# from backend import run_travel_agent
# user_input = input("Enter travel request: ")

# response = run_travel_agent(
#     user_input=user_input,
#     thread_id="test_user"
# )

# print("\nFINAL RESPONSE:\n")
# print(response["answer"])

from mcp_client import get_all_tools

asyncio.run(get_all_tools())
# asyncio.run(get_tavily_search_tool())
# asyncio.run(tavily_mcp_search("What is the capital of France?"))
