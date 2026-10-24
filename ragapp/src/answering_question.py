from langgraph.graph import END, START, StateGraph

try:
    from edges import route_messages
except ImportError:
    from utils.edges import route_messages

try:
    from nodes import (
        generate_answer,
        generate_question,
        save_interview,
        search_web,
        search_web2,
        search_web3,
        write_section,
    )
except ImportError:
    from utils.nodes import (
        generate_answer,
        generate_question,
        save_interview,
        search_web,
        search_web2,
        search_web3,
        write_section,
    )

try:
    from state import InterviewInputState, InterviewState
except ImportError:
    from utils.state import InterviewInputState, InterviewState

# Add nodes and edges
interview_builder = StateGraph(state_schema=InterviewState, input_schema=InterviewInputState)
interview_builder.add_node("ask_question", generate_question)
interview_builder.add_node("search_web", search_web)
interview_builder.add_node("search_web2", search_web2)
interview_builder.add_node("search_web3", search_web3)
interview_builder.add_node("answer_question", generate_answer)
interview_builder.add_node("save_interview", save_interview)
interview_builder.add_node("write_section", write_section)

# Flow
interview_builder.add_edge(START, "ask_question")
interview_builder.add_edge("ask_question", "search_web")
interview_builder.add_edge("ask_question", "search_web2")
interview_builder.add_edge("ask_question", "search_web3")
interview_builder.add_edge("search_web", "answer_question")
interview_builder.add_edge("search_web2", "answer_question")
interview_builder.add_edge("search_web3", "answer_question")
interview_builder.add_conditional_edges(
    "answer_question", route_messages, ["ask_question", "save_interview"]
)
interview_builder.add_edge("save_interview", "write_section")
interview_builder.add_edge("write_section", END)

question_answer_graph = interview_builder.compile()
answering_questions = question_answer_graph
