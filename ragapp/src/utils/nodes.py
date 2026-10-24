from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.messages.utils import get_buffer_string
from langchain_tavily import TavilySearch
from langgraph.types import interrupt
from model import llm
from objects import Analyst, Perspectives, SearchQuery
from prompt import (
    analyst_instructions,
    answer_instructions,
    question_instructions,
    search_instructions,
    section_writer_instructions,
)
from state import GeneralGenerateAnalystState, InterviewState

load_dotenv()


def create_analyst_node(state: GeneralGenerateAnalystState):
    topic = state["topic"]
    max_analysts = state["max_analysts"]
    human_analyst_feedback = state.get("human_analyst_feedback")
    # Enforce structer outpu
    structred_llm = llm.with_structured_output(Perspectives)
    # system message

    system_message = analyst_instructions.format(
        topic=topic,
        human_analyst_feedback=human_analyst_feedback or "None",
        max_analysts=max_analysts,
    )
    analysts = structred_llm.invoke(
        [SystemMessage(content=system_message)]
        + [HumanMessage(content="please generete the list of analyst")]
    )
    return {"analysts": analysts.analyst}


create_analysts = create_analyst_node


def human_feedback(state: GeneralGenerateAnalystState):
    """this where the human gives feedback about the analyst"""
    feedback = interrupt(
        {
            "question": "Are these analysts good for the topic?",
            "analysts": [
                analyst.model_dump() if hasattr(analyst, "model_dump") else analyst
                for analyst in state.get("analysts", [])
            ],
            "instructions": "Return feedback to regenerate analyst or return empty/perfect/continue/ok to approve and continue the graph",
        }
    )

    if feedback is None:
        return {"human_analyst_feedback": None}

    if isinstance(feedback, dict):
        feedback = (
            feedback.get("feedback") or feedback.get("human_analyst_feedback") or ""
        )

    if isinstance(feedback, str):
        cleaned = feedback.strip()
        if not cleaned or cleaned.lower() in {
            "perfect",
            "ok",
            "continue",
            "yes",
            "looks good",
            "approved",
        }:
            return {"human_analyst_feedback": None}
        return {"human_analyst_feedback": cleaned}

    return {"human_analyst_feedback": None}


def _resolve_analyst(state) -> Analyst:
    analyst_data = state.get("analyst") if isinstance(state, dict) else state
    if isinstance(analyst_data, Analyst):
        return analyst_data
    if isinstance(analyst_data, dict):
        return Analyst.model_validate(analyst_data)
    if isinstance(analyst_data, str) and analyst_data.strip():
        name = state.get("name") if isinstance(state, dict) else None
        role = state.get("role") if isinstance(state, dict) else None
        affiliation = state.get("affiliation") if isinstance(state, dict) else None
        return Analyst(
            name=name or "Research Analyst",
            role=role or "Specialist",
            affiliation=affiliation or "Research Group",
            description=analyst_data,
        )
    if isinstance(state, dict):
        name = state.get("name")
        role = state.get("role")
        affiliation = state.get("affiliation")
        description = state.get("description") or state.get("discription")
        if any([name, role, affiliation, description]):
            return Analyst(
                name=name or "Research Analyst",
                role=role or "Research Analyst",
                affiliation=affiliation or "Research Group",
                description=description or "Expert research analyst investigating this domain",
            )
    return Analyst(
        name="Research Analyst",
        role="Research Analyst",
        affiliation="Research Group",
        description="Expert research analyst investigating this domain",
    )


def generate_question(state: InterviewState):
    """node to generete the questions"""
    analyst = _resolve_analyst(state)
    messages = state.get("messages") or []

    # generate questions
    system_message = question_instructions.format(goals=analyst.persona)
    input_messages = [SystemMessage(content=system_message)] + (
        messages if messages else [HumanMessage(content="Please begin the interview.")]
    )
    question = llm.invoke(input_messages)

    return {"messages": [question]}


def search_web(state: InterviewState):
    """Retrive docs from the web"""
    messages = state.get("messages") or []
    structred_llm = llm.with_structured_output(SearchQuery)
    search_instructions_system_message = SystemMessage(content=search_instructions)
    input_messages = [search_instructions_system_message] + (
        messages if messages else [HumanMessage(content="Initial research query")]
    )
    search_query = structred_llm.invoke(input_messages)

    try:
        tavily_search = TavilySearch(max_results=3)
        data = tavily_search.invoke({"query": search_query.search_query})
        search_docs = data.get("results", data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        formatted_search_docs = "\n\n---\n\n".join(
            [
                f'<Document href="{doc.get("url", "")}"/>\n{doc.get("content", "")}\n</Document>'
                for doc in search_docs if isinstance(doc, dict)
            ]
        )
    except Exception as e:
        formatted_search_docs = f'<Document href="web"/>\nSearch results for "{search_query.search_query}": {e}\n</Document>'

    return {"context": [formatted_search_docs]}


def search_web2(state: InterviewState):
    """Retrive docs from the web"""
    messages = state.get("messages") or []
    structred_llm = llm.with_structured_output(SearchQuery)
    search_instructions_system_message = SystemMessage(content=search_instructions)
    input_messages = [search_instructions_system_message] + (
        messages if messages else [HumanMessage(content="Initial research query")]
    )
    search_query = structred_llm.invoke(input_messages)

    try:
        tavily_search = TavilySearch(max_results=3)
        data = tavily_search.invoke({"query": search_query.search_query})
        search_docs = data.get("results", data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        formatted_search_docs = "\n\n---\n\n".join(
            [
                f'<Document href="{doc.get("url", "")}"/>\n{doc.get("content", "")}\n</Document>'
                for doc in search_docs if isinstance(doc, dict)
            ]
        )
    except Exception as e:
        formatted_search_docs = f'<Document href="web"/>\nSearch results for "{search_query.search_query}": {e}\n</Document>'

    return {"context": [formatted_search_docs]}


def search_web3(state: InterviewState):
    """Retrive docs from the web"""
    messages = state.get("messages") or []
    structred_llm = llm.with_structured_output(SearchQuery)
    search_instructions_system_message = SystemMessage(content=search_instructions)
    input_messages = [search_instructions_system_message] + (
        messages if messages else [HumanMessage(content="Initial research query")]
    )
    search_query = structred_llm.invoke(input_messages)

    try:
        tavily_search = TavilySearch(max_results=3)
        data = tavily_search.invoke({"query": search_query.search_query})
        search_docs = data.get("results", data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        formatted_search_docs = "\n\n---\n\n".join(
            [
                f'<Document href="{doc.get("url", "")}"/>\n{doc.get("content", "")}\n</Document>'
                for doc in search_docs if isinstance(doc, dict)
            ]
        )
    except Exception as e:
        formatted_search_docs = f'<Document href="web"/>\nSearch results for "{search_query.search_query}": {e}\n</Document>'

    return {"context": [formatted_search_docs]}


def generate_answer(state: InterviewState):
    """Node to answer the questions"""
    analyst = _resolve_analyst(state)
    messages = state.get("messages") or []
    context = state.get("context") or []

    # answer the question_instructions
    system_message = answer_instructions.format(goals=analyst.persona, context=context)
    input_messages = [SystemMessage(content=system_message)] + (
        messages if messages else [HumanMessage(content="What are the key insights?")]
    )
    answer = llm.invoke(input_messages)
    # name the message coming from the expert
    answer.name = "expert"
    # append to the state
    return {"messages": [answer]}


def save_interview(state: InterviewState):
    """save interver"""
    messages = state.get("messages") or []
    interview = get_buffer_string(messages)
    return {"interview": interview}


save_answer = save_interview


def write_section(state: InterviewState):
    """Node to answer a question"""
    interview = state.get("interview") or ""
    context = state.get("context") or []
    analyst = _resolve_analyst(state)

    system_message = section_writer_instructions.format(focus=analyst.description)
    source_context = context if context else interview
    section = llm.invoke(
        [SystemMessage(content=system_message)]
        + [HumanMessage(content=f"Use this source to write your section:\n{source_context}")]
    )
    return {"sections": [section.content]}
