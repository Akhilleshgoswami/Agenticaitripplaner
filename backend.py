import os
import operator
import uuid

import certifi
import psycopg

from dotenv import load_dotenv
from typing import TypedDict, Annotated

from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from langchain_groq import ChatGroq

from tools.travily_tool import travily_serach
from tools.flight_tool import search_flights


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


# ============================================================
# DATABASE
# ============================================================

def get_db_url() -> str:
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        raise ValueError("DATABASE_URL not set")

    if "sslmode=" not in db_url:
        separator = "&" if "?" in db_url else "?"
        db_url = f"{db_url}{separator}sslmode=require"

    return db_url


# ============================================================
# API KEYS
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set")


# ============================================================
# LLM
# ============================================================

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=GROQ_API_KEY,
    temperature=0,
)


# ============================================================
# STATE
# ============================================================

class TravelState(TypedDict):
    message: Annotated[list[AnyMessage], operator.add]

    user_query: str

    flight_results: str

    hotel_results: str

    itinerary: str

    llm_calls: int


# ============================================================
# FLIGHT AGENT
# ============================================================

def flight_agent(state: TravelState):

    print("✈️ Searching flights...")

    query = state["user_query"]

    try:
        flight_data = search_flights(query)

    except Exception as e:

        print(f"❌ Flight search failed: {e}")

        flight_data = f"Flight search failed: {str(e)}"

    print("✅ Flight search completed")

    return {
        "flight_results": flight_data,
    }


# ============================================================
# HOTEL AGENT
# ============================================================

def hotel_agent(state: TravelState):

    print("🏨 Searching hotels...")

    query = f"Best hotels for this travel request:\n{state['user_query']}"

    try:
        hotel_data = travily_serach(query)

    except Exception as e:

        print(f"❌ Hotel search failed: {e}")

        hotel_data = f"Hotel search failed: {str(e)}"

    print("✅ Hotel search completed")

    return {
        "hotel_results": hotel_data,
    }


# ============================================================
# FINAL / ITINERARY AGENT
# ============================================================

def itinerary_agent(state: TravelState):

    print("🤖 Generating travel plan...")

    prompt = f"""
Create a complete travel plan using the information below.

USER REQUEST:
{state["user_query"]}

FLIGHT RESULTS:
{state["flight_results"]}

HOTEL RESULTS:
{state["hotel_results"]}

Create a practical, budget-aware travel response.

Use these sections:

1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Day-by-Day Itinerary
5. Estimated Budget
6. Final Recommendations

Important:

- Do not invent flight prices.
- If flight pricing is unavailable, clearly say so.
- Do not invent hotel prices if they are unavailable.
- Clearly distinguish search results from estimates.
- Keep the response practical.
"""

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are a professional AI travel planning assistant. "
                    "Use the provided search results carefully and never "
                    "invent unavailable information."
                )
            ),
            HumanMessage(content=prompt),
        ]
    )

    print("✅ Travel plan generated")

    return {
        "itinerary": response.content,
        "message": [AIMessage(content=response.content)],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# ============================================================
# BUILD GRAPH
# ============================================================

graph = StateGraph(TravelState)


graph.add_node(
    "flight_agent",
    flight_agent,
)

graph.add_node(
    "hotel_agent",
    hotel_agent,
)

graph.add_node(
    "itinerary_agent",
    itinerary_agent,
)


# ============================================================
# GRAPH FLOW
# ============================================================

# Both agents start at the same time.
graph.add_edge(
    START,
    "flight_agent",
)

graph.add_edge(
    START,
    "hotel_agent",
)

# Both must finish before itinerary_agent runs.
graph.add_edge(
    "flight_agent",
    "itinerary_agent",
)

graph.add_edge(
    "hotel_agent",
    "itinerary_agent",
)

graph.add_edge(
    "itinerary_agent",
    END,
)


# ============================================================
# POSTGRES CHECKPOINT
# ============================================================

DATABASE_URL = get_db_url()

connection = psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row,
)

checkpointer = PostgresSaver(connection)

# Run once when setting up the database.
checkpointer.setup()


# ============================================================
# COMPILE GRAPH
# ============================================================

travel_graph = graph.compile(
    checkpointer=checkpointer,
)


# ============================================================
# RUN TRAVEL AGENT
# ============================================================

def run_travel_agent(
    user_input: str,
    thread_id: str | None = None,
):

    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    initial_state: TravelState = {
        "message": [
            HumanMessage(
                content=user_input
            )
        ],

        "user_query": user_input,

        "flight_results": "",

        "hotel_results": "",

        "itinerary": "",

        "llm_calls": 0,
    }

    print("\n🚀 Starting travel agent...\n")

    result = travel_graph.invoke(
        initial_state,
        config=config,
    )

    print("\n🎉 Travel agent completed\n")

    return {
        "thread_id": thread_id,

        "answer": result.get(
            "itinerary",
            "",
        ),
        "itinerary": result.get("itinerary", ""),
        "flight_results": result.get(
            "flight_results",
            "",
        ),

        "hotel_results": result.get(
            "hotel_results",
            "",
        ),

        "llm_calls": result.get(
            "llm_calls",
            0,
        ),
    }