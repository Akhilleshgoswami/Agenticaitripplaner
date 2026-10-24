import operator
from typing import Annotated, List

from langgraph.graph import MessagesState
from typing_extensions import NotRequired, Optional, TypedDict

try:
    from utils.objects import Analyst
except ImportError:
    from objects import Analyst


class GeneralGenerateAnalystState(TypedDict):
    topic: str  # research topic
    max_analysts: int  # maximum number of analysts to generate
    human_analyst_feedback: NotRequired[Optional[str]]  # human feedback on the analysts
    analysts: NotRequired[List[Analyst]]  # list of all analysts


class InterviewInputState(MessagesState):
    analyst: NotRequired[Analyst]  # nested analyst object
    name: NotRequired[str]  # analyst name
    role: NotRequired[str]  # analyst role
    affiliation: NotRequired[str]  # analyst affiliation
    description: NotRequired[str]  # analyst description
    max_number_turn: NotRequired[int]  # number turns of conversation


class InterviewState(MessagesState):
    max_number_turn: NotRequired[Optional[int]]  # number turns of conversation
    context: NotRequired[Annotated[list, operator.add]]  # source of docs
    analyst: NotRequired[Optional[Analyst]]  # my analyst
    name: NotRequired[Optional[str]]
    role: NotRequired[Optional[str]]
    affiliation: NotRequired[Optional[str]]
    description: NotRequired[Optional[str]]
    interview: NotRequired[Optional[str]]  # interview transcript
    sections: NotRequired[Optional[list]]  # final key we duplicated in outer state for send() api
