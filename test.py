# response = serach("What is the capital of France?")
# print(response)
# print(search_flights("Plan a 7 days Japan trip from Bangladesh"))
from backend import run_travel_agent
from tools.flight_tool import search_flights

user_input = input("Enter travel request")
res = run_travel_agent(user_input, thread_id="userOd")
print(res)
