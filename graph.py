"""
LangGraph Workflow: 4 Roles with Evaluator-Optimizer Loop
---------------------------------------------------------
Nodes:
  1. researcher : Discovers merged PRs using GitHub REST & page fetch tools.
  2. drafter    : Generates and refines plain-language release notes.
  3. checker    : Audits draft against rules (no invented lines, no missing PRs).
  4. reporter   : Produces final executive report, token cost table, and summary.

Conditional Edge:
  - If checker passes -> reporter
  - If checker rejects and retries < max_retries -> drafter (with checker feedback)
  - If checker rejects and retries >= max_retries -> reporter (status FAILED)
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from state import AgentState
from config import MAX_RETRIES
from nodes import researcher_node, drafter_node, checker_node, reporter_node


def route_after_checker(state: AgentState) -> Literal["drafter", "reporter"]:
    """
    Evaluator-Optimizer router:
    Directs workflow to Drafter for revision if rejected, or to Reporter when passed/exhausted.
    """
    passed = state.get("checker_passed", False)
    retries = state.get("retry_count", 0)
    max_retries = state.get("max_retries", MAX_RETRIES)

    if passed:
        print(f"\n[Router] Checker APPROVED the draft. Advancing to Reporter.")
        return "reporter"

    if retries >= max_retries:
        print(f"\n[Router] Maximum retries ({max_retries}) reached without passing. Advancing to Reporter with FAILED status.")
        return "reporter"

    print(f"\n[Router] Draft REJECTED. Routing back to Drafter for revision (Retry {retries}/{max_retries}).")
    return "drafter"


def build_pr_summarizer_graph():
    """Builds and compiles the LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # Add the 4 role nodes
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("drafter", drafter_node)
    workflow.add_node("checker", checker_node)
    workflow.add_node("reporter", reporter_node)

    # Define edges
    # START -> researcher -> drafter -> checker
    workflow.add_edge(START, "researcher")
    workflow.add_edge("researcher", "drafter")
    workflow.add_edge("drafter", "checker")

    # Conditional edge after checker
    workflow.add_conditional_edges(
        "checker",
        route_after_checker,
        {
            "drafter": "drafter",
            "reporter": "reporter"
        }
    )

    # reporter -> END
    workflow.add_edge("reporter", END)

    return workflow.compile()


# Pre-compiled graph instance
app = build_pr_summarizer_graph()
