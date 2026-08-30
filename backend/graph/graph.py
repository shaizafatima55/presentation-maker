from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from .state import PresentationState
from .nodes import (
    input_node, search_node, extract_node, prioritization_node,
    plan_review_node, synthesis_node, tone_node, final_node
)

builder = StateGraph(PresentationState)

builder.add_node("input", input_node)
builder.add_node("search", search_node)
builder.add_node("extract", extract_node)
builder.add_node("prioritization", prioritization_node)
builder.add_node("plan_review", plan_review_node)
builder.add_node("synthesis", synthesis_node)
builder.add_node("tone", tone_node)
builder.add_node("final", final_node)

builder.add_edge(START, "input")
builder.add_edge("input", "search")
builder.add_edge("search", "extract")
builder.add_edge("extract", "prioritization")
builder.add_edge("prioritization", "plan_review")
builder.add_edge("plan_review", "synthesis")
builder.add_edge("synthesis", "tone")
builder.add_edge("tone", "final")
builder.add_edge("final", END)

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)
