import operator
import os
import uuid
from typing import Annotated, TypedDict

import psycopg
from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg.rows import dict_row

from tools.flight_tool import search_flights
from tools.tavily_tool import search


def db_url():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")

    if "sslmode" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url += f"{separator}sslmode=require"

    return database_url


OPEN_AI_MODEL = "gpt-4o-mini"
OPEN_AI_API_KEY = os.getenv("OPEN_AI_API_KEY")

if not OPEN_AI_API_KEY:
    raise ValueError("OPEN_AI_API_KEY is not set")

llm = ChatOpenAI(model=OPEN_AI_MODEL, api_key=OPEN_AI_API_KEY)


# StateGraph
class TravleState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_search_results: str
    hotel_search_results: str
    itinerary: str
    llm_calls: int


def flight_agent(state: TravleState):
    query = state["user_query"]
    flight_data = search_flights(query)
    return {
        "flight_search_results": flight_data,
        "message": [AIMessage(content="flight result fetched")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def hotel_agent(state: TravleState):
    query = state["user_query"]
    hotel_data = search(query)
    return {
        "hotel_search_results": hotel_data,
        "message": [AIMessage(content="hotel  result fetched")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def itinerary_agent(state: TravleState):
    prompt = f"""
Create a complete travel itinerary.

User Query:
{state["user_query"]}

Flight Results:
{state["flight_search_results"]}

Hotel Results:
{state["hotel_search_results"]}

Make the itinerary practical, budget-aware, and easy to follow.
"""

    response = llm.invoke(
        [
            SystemMessage(content="You are an expert travel planner."),
            HumanMessage(content=prompt),
        ]
    )

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def final_agent(state: TravleState):

    final_prompt = f"""
Generate the final travel response for the user.

User Request:
{state["user_query"]}

Flights:
{state["flight_search_results"]}

Hotels:
{state["hotel_search_results"]}

Itinerary:
{state["itinerary"]}

Format the final answer beautifully using these sections:

1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Day-by-Day Itinerary
5. Estimated Budget
6. Final Recommendations

Important:
- Be clear and practical.
- Mention that live flight API may not provide ticket prices if pricing is unavailable.
- Keep the response useful for real travel planning.
"""

    response = llm.invoke(
        [
            SystemMessage(
                content="You are a professional AI travel booking assistant."
            ),
            HumanMessage(content=final_prompt),
        ]
    )

    return {"messages": [response], "llm_calls": state.get("llm_calls", 0) + 1}


graph = StateGraph(TravleState)
graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)
graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)

database_url = db_url()
_conn = psycopg.connect(database_url, autocommit=True, row_factory=dict_row)
checkpointer = PostgresSaver(_conn)
checkpointer.setup()

travel_graph = graph.compile(checkpointer=checkpointer)


def run_travel_agent(user_input: str, thread_id: str | None = None):
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {"configurable": {"thread_id": thread_id}}

    result = travel_graph.invoke(
        {
            "messages": [HumanMessage(content=user_input)],
            "user_query": user_input,
            "flight_search_results": "",
            "hotel_search_results": "",
            "itinerary": "",
            "llm_calls": 0,
        },
        config=config,
    )

    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_search_results", result.get("flight_results", "")),
        "hotel_results": result.get("hotel_search_results", result.get("hotel_results", "")),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }
