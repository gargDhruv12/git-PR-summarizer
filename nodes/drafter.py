"""
Role 2: DRAFTER Node
--------------------
Writes release notes grouped into three mandatory sections:
  1. Features
  2. Fixes
  3. Breaking Changes

Rules:
- Every line MUST include its PR number (e.g., `- [#123] Added dark mode support`).
- Plain language that a normal user can easily understand.
- Produces a first draft, then refines it once (write, then improve).
- If the Checker sends feedback, the Drafter directly addresses the feedback,
  pruning invented lines and incorporating any missing PRs.
"""

import json
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from config import get_llm, calculate_cost, execute_with_retry
from models import ReleaseNotesDraft
from state import AgentState


def _format_markdown(draft: ReleaseNotesDraft) -> str:
    """Formats structured release notes into clean markdown."""
    lines = ["# Release Notes\n"]
    
    lines.append("## Features")
    if draft.features:
        for item in draft.features:
            lines.append(item if item.strip().startswith("-") else f"- {item}")
    else:
        lines.append("- None in this release")
    lines.append("")

    lines.append("## Fixes")
    if draft.fixes:
        for item in draft.fixes:
            lines.append(item if item.strip().startswith("-") else f"- {item}")
    else:
        lines.append("- None in this release")
    lines.append("")

    lines.append("## Breaking Changes")
    if draft.breaking_changes:
        for item in draft.breaking_changes:
            lines.append(item if item.strip().startswith("-") else f"- {item}")
    else:
        lines.append("- None in this release")
    lines.append("")

    return "\n".join(lines)


def drafter_node(state: AgentState) -> Dict[str, Any]:
    print("\n" + "=" * 65)
    print("-> [ROLE 2: DRAFTER] Drafting / Refining Release Notes")
    print("=" * 65)

    prs = state.get("researcher_prs", [])
    feedback = state.get("checker_feedback")
    prev_draft = state.get("current_draft")
    retry_count = state.get("retry_count", 0)

    llm = get_llm(temperature=0.2)
    structured_llm = llm.with_structured_output(ReleaseNotesDraft, include_raw=True)

    in_tokens = 0
    out_tokens = 0

    prs_summary = json.dumps(prs, indent=2)

    system_prompt = (
        "You are the Drafter agent in a release note generation system.\n"
        "Your task is to write user-friendly release notes grouped strictly into three sections:\n"
        "1. Features\n"
        "2. Fixes\n"
        "3. Breaking Changes\n\n"
        "CRITICAL RULES:\n"
        "- Every single bullet line MUST include the PR number it came from, formatted as `[#PR_NUMBER]` or `(#PR_NUMBER)`.\n"
        "  Example: '- [#101] Added automatic dark mode toggle for users.'\n"
        "- Plain language: Explain the value to normal users, avoiding deep internal implementation jargon.\n"
        "- ONLY include real PRs from the researcher's list. Never invent PRs or features.\n"
        "- Every merged PR in the list MUST be included in exactly one appropriate section."
    )

    if feedback and prev_draft:
        # We are revising based on Checker's rejection feedback
        print(f"[Drafter] Revising draft based on Checker rejection (Attempt #{retry_count})...")
        print(f"[Drafter] Checker Feedback: {feedback}")

        revision_prompt = (
            f"Here is the verified list of merged PRs from the Researcher:\n{prs_summary}\n\n"
            f"The previous draft was REJECTED by the Checker with this feedback:\n"
            f"{feedback}\n\n"
            f"Previous rejected draft was:\n{prev_draft}\n\n"
            "Please fix the draft according to the feedback:\n"
            "- REMOVE any invented/hallucinated lines or nonexistent PR numbers.\n"
            "- ADD any missing PRs from the researcher's list.\n"
            "- Ensure EVERY bullet point explicitly contains its real PR number (e.g. `[#101] ...`).\n"
            "- Group cleanly into Features, Fixes, and Breaking Changes."
        )

        res = execute_with_retry(lambda: structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=revision_prompt)
        ]))

        u = getattr(res["raw"], "usage_metadata", {}) or {}
        in_tokens += u.get("input_tokens", 0)
        out_tokens += u.get("output_tokens", 0)
        final_draft_model: ReleaseNotesDraft = res["parsed"]

    else:
        # Initial draft generation (write, then refine once)
        print("[Drafter] Step A: Writing initial release notes draft...")
        initial_prompt = (
            f"Here are the merged PRs for the week:\n{prs_summary}\n\n"
            "Write the first draft of the release notes.\n"
            "Group into Features, Fixes, and Breaking Changes.\n"
            "Make sure every line mentions its PR number like `[#101]` and is written in clear, plain language."
        )

        res1 = execute_with_retry(lambda: structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=initial_prompt)
        ]))
        u1 = getattr(res1["raw"], "usage_metadata", {}) or {}
        in_tokens += u1.get("input_tokens", 0)
        out_tokens += u1.get("output_tokens", 0)
        draft1: ReleaseNotesDraft = res1["parsed"]
        draft1_md = _format_markdown(draft1)

        print("[Drafter] Step B: Refining draft (write, then improve once)...")
        refine_prompt = (
            f"Here is the first draft of release notes:\n{draft1_md}\n\n"
            f"And here is the verified researcher PR list:\n{prs_summary}\n\n"
            "Refine and polish this draft:\n"
            "1. Simplify any remaining developer jargon into natural user-friendly language.\n"
            "2. Verify that every single line has a clear PR number like `[#PR_NUMBER]`.\n"
            "3. Double check that all PRs from the researcher list are present and none are omitted."
        )

        res2 = execute_with_retry(lambda: structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=refine_prompt)
        ]))
        u2 = getattr(res2["raw"], "usage_metadata", {}) or {}
        in_tokens += u2.get("input_tokens", 0)
        out_tokens += u2.get("output_tokens", 0)
        final_draft_model: ReleaseNotesDraft = res2["parsed"]

    formatted_md = _format_markdown(final_draft_model)
    cost = calculate_cost(in_tokens, out_tokens)

    # Accumulate token usage
    token_usage = state.get("token_usage_by_agent", {})
    existing_drafter_usage = token_usage.get("Drafter", {"input_tokens": 0, "output_tokens": 0})
    token_usage["Drafter"] = {
        "input_tokens": existing_drafter_usage["input_tokens"] + in_tokens,
        "output_tokens": existing_drafter_usage["output_tokens"] + out_tokens,
    }

    cost_by_agent = state.get("cost_by_agent", {})
    cost_by_agent["Drafter"] = cost_by_agent.get("Drafter", 0.0) + cost

    history = state.get("draft_history", [])
    history.append(formatted_md)

    print(f"[Drafter Generated Draft]:\n{formatted_md}")
    print(f"[Drafter Telemetry] Turn Tokens: {in_tokens} in / {out_tokens} out | Turn Cost: ${cost:.6f}")

    return {
        "current_draft": formatted_md,
        "draft_history": history,
        "draft_features": final_draft_model.features,
        "draft_fixes": final_draft_model.fixes,
        "draft_breaking_changes": final_draft_model.breaking_changes,
        "token_usage_by_agent": token_usage,
        "cost_by_agent": cost_by_agent,
    }
