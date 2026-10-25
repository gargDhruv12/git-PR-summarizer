"""
Role 4: REPORTER Node
---------------------
Produces the comprehensive final run summary:
  - What each agent did (Researcher, Drafter, Checker)
  - What was rejected and why (rejection audit log)
  - Full cost and token telemetry (tokens & money per agent and total)
  - Open doubts and caveats
  - Final accepted or latest release notes
"""

from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from config import get_llm, calculate_cost, execute_with_retry, GEMINI_MODEL
from state import AgentState


def reporter_node(state: AgentState) -> Dict[str, Any]:
    print("\n" + "=" * 65)
    print("-> [ROLE 4: REPORTER] Generating Pipeline Summary & Telemetry Report")
    print("=" * 65)

    repo = state.get("repo_name", "pallets/flask")
    week_start = state.get("week_start", "")
    week_end = state.get("week_end", "")
    researcher_prs = state.get("researcher_prs", [])
    current_draft = state.get("current_draft", "")
    checker_passed = state.get("checker_passed", False)
    retry_count = state.get("retry_count", 0)
    rejection_history = state.get("rejection_history", [])
    token_usage = state.get("token_usage_by_agent", {})
    cost_by_agent = state.get("cost_by_agent", {})
    status = "PASSED" if checker_passed else "FAILED"

    # Reporter LLM Call to generate synthesis and open doubts
    llm = get_llm(temperature=0.2)

    reporter_prompt = (
        "You are the Reporter agent. Synthesize the run into an executive summary.\n"
        f"Repository: {repo} | Window: {week_start} to {week_end}\n"
        f"Pipeline Outcome: {status} (Retries Used: {retry_count})\n"
        f"Total PRs Discovered: {len(researcher_prs)}\n"
        f"Rejection History: {rejection_history}\n\n"
        "Draft Content:\n"
        f"{current_draft}\n\n"
        "Instructions:\n"
        "1. Summarize agent actions: What Researcher did, what Drafter did, what Checker evaluated.\n"
        "2. Detail any rejections: What was rejected and why.\n"
        "3. Identify 'Open Doubts': Any subtle ambiguities in PR descriptions, versioning implications, "
        "or potential user misunderstandings."
    )

    res = execute_with_retry(lambda: llm.invoke([
        SystemMessage(content="You are an expert technical reporter providing transparent audit summaries."),
        HumanMessage(content=reporter_prompt)
    ]))

    u = getattr(res, "usage_metadata", {}) or {}
    rep_in = u.get("input_tokens", 0)
    rep_out = u.get("output_tokens", 0)
    rep_cost = calculate_cost(rep_in, rep_out)

    token_usage["Reporter"] = {"input_tokens": rep_in, "output_tokens": rep_out}
    cost_by_agent["Reporter"] = rep_cost

    # Extract text cleanly in case model returns parts list
    content_text = ""
    if isinstance(res.content, list):
        for part in res.content:
            if isinstance(part, dict) and "text" in part:
                content_text += part["text"]
            elif isinstance(part, str):
                content_text += part
    else:
        content_text = str(res.content)

    # Aggregate totals
    total_in = sum(v.get("input_tokens", 0) for v in token_usage.values())
    total_out = sum(v.get("output_tokens", 0) for v in token_usage.values())
    total_cost = sum(cost_by_agent.values())

    telemetry_table = []
    telemetry_table.append("| Agent Role  | Input Tokens | Output Tokens | Total Tokens | Estimated Cost (USD) |")
    telemetry_table.append("|-------------|--------------|---------------|--------------|----------------------|")
    for role in ["Researcher", "Drafter", "Checker", "Reporter"]:
        role_usage = token_usage.get(role, {"input_tokens": 0, "output_tokens": 0})
        rin = role_usage.get("input_tokens", 0)
        rout = role_usage.get("output_tokens", 0)
        rcost = cost_by_agent.get(role, 0.0)
        telemetry_table.append(f"| {role:<11} | {rin:<12} | {rout:<13} | {rin + rout:<12} | ${rcost:.6f}            |")
    telemetry_table.append(f"| **TOTAL**   | **{total_in}**        | **{total_out}**         | **{total_in + total_out}**       | **${total_cost:.6f}**         |")
    table_str = "\n".join(telemetry_table)

    # Rejection section
    rejection_text = "None! The draft passed on the first attempt without rejections."
    if rejection_history:
        rejection_lines = []
        for r in rejection_history:
            rejection_lines.append(f"- **Attempt #{r['attempt']}**: {r['feedback']}")
            if r.get("invented_lines"):
                rejection_lines.append(f"  * Invented lines removed: {r['invented_lines']}")
            if r.get("missing_prs"):
                rejection_lines.append(f"  * Missing PRs added: {r['missing_prs']}")
        rejection_text = "\n".join(rejection_lines)

    # Assemble complete report
    final_report = f"""
================================================================================
                    GIT PR SUMMARIZER - PIPELINE RUN REPORT
================================================================================
Target Repository : {repo}
Timeframe         : {week_start} to {week_end}
Overall Status    : {status}
Retries Used      : {retry_count}
Gemini Model      : {GEMINI_MODEL}

--------------------------------------------------------------------------------
1. AGENT WORKFLOW & ACTIONS
--------------------------------------------------------------------------------
{content_text}

--------------------------------------------------------------------------------
2. REJECTION LOG & QUALITY AUDIT
--------------------------------------------------------------------------------
{rejection_text}

--------------------------------------------------------------------------------
3. TOKEN USAGE & COST TELEMETRY
--------------------------------------------------------------------------------
{table_str}

--------------------------------------------------------------------------------
4. FINAL RELEASE NOTES
--------------------------------------------------------------------------------
{current_draft}
================================================================================
"""

    print(final_report)

    return {
        "status": status,
        "token_usage_by_agent": token_usage,
        "cost_by_agent": cost_by_agent,
        "total_tokens": {"input_tokens": total_in, "output_tokens": total_out, "total": total_in + total_out},
        "total_cost_usd": round(total_cost, 6),
        "final_report": final_report,
        "reporter_summary": content_text,
    }
