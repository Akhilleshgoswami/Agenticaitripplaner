from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.graph import END

from utils.state import InterviewState

try:
    from state import GeneralGenerateAnalystState
except ImportError:
    from utils.state import GeneralGenerateAnalystState

load_dotenv()


# conditional edgs
def should_continue(
    state: GeneralGenerateAnalystState,
) -> Literal["create_analysts", END]:
    """Return the next node to excute"""
    human_analyst_feedback = state.get("human_analyst_feedback", None)
    if human_analyst_feedback:
        return "create_analysts"
    return END


def routes_messages(state: InterviewState, name: str = "expert"):
    """Route between questions and answer"""
    message = state.get("messages") or []
    max_num_turn = state.get("max_number_turn", state.get("max_num_turn", 2))
    num_response = sum(
        1 for m in message if isinstance(m, AIMessage) and getattr(m, "name", None) == name
    )
    if num_response >= max_num_turn:
        return "save_interview"
    return "ask_question"


route_messages = routes_messages
