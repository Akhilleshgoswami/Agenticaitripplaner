import os

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

try:
    from edges import should_continue
except ImportError:
    from utils.edges import should_continue

try:
    from nodes import create_analyst_node, human_feedback
    from state import GeneralGenerateAnalystState
except ImportError:
    from utils.nodes import create_analyst_node, human_feedback
    from utils.state import GeneralGenerateAnalystState

load_dotenv()

builder = StateGraph(GeneralGenerateAnalystState)

builder.add_node("create_analysts", create_analyst_node)
builder.add_node("human_feedback", human_feedback)
builder.add_edge(START, "create_analysts")
builder.add_edge("create_analysts", "human_feedback")
builder.add_conditional_edges("human_feedback", should_continue)
graph = builder.compile()
