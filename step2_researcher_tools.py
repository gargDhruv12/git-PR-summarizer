"""
Step 2: Researcher with Bound Tools (GitHub API & Page Fetch)
-------------------------------------------------------------
Tests binding tools to Gemini. The model autonomously decides to call
`fetch_github_prs` and optionally `fetch_web_page`, processes the returned data,
and produces structured JSON containing only PRs merged within the specified date range.
Also tracks token counts and costs across all tool execution turns.
"""

import json
from datetime import datetime
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from config import get_llm, calculate_cost, execute_with_retry, GEMINI_MODEL
from tools import ALL_TOOLS, fetch_github_prs, fetch_web_page
from models import ResearcherOutput


def run_researcher_with_tools(repo: str = "pallets/flask", week_start: str = "2026-10-01", week_end: str = "2026-10-08"):
    print("=" * 65)
    print(f"STEP 2: Researcher with Bound Tools")
    print(f"Repository: {repo} | Date Range: {week_start} to {week_end}")
    print(f"Model: {GEMINI_MODEL}")
    print("=" * 65)

    llm = get_llm(temperature=0.2)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    tool_map = {t.name: t for t in ALL_TOOLS}

    total_input_tokens = 0
    total_output_tokens = 0

    system_prompt = (
        "You are the Researcher agent. Your mission is to discover all pull requests for the repository "
        f"'{repo}' that were MERGED between {week_start} and {week_end} (inclusive).\n"
        "Instructions:\n"
        "1. Use the `fetch_github_prs` tool to get the repository's pull requests.\n"
        "2. If needed, inspect specific details with `fetch_web_page`.\n"
        "3. Filter strictly: ONLY include PRs that have a non-null `merged_at` timestamp "
        f"falling within {week_start} to {week_end}.\n"
        "4. Summarize each merged PR clearly for release notes."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Please gather all pull requests merged in '{repo}' between {week_start} and {week_end}.")
    ]

    # Tool calling loop (up to 4 steps)
    for step in range(4):
        print(f"\n[Turn {step+1}] Invoking Gemini with bound tools...")
        response = execute_with_retry(lambda: llm_with_tools.invoke(messages))
        messages.append(response)

        # Track usage
        usage = getattr(response, "usage_metadata", {}) or {}
        in_t = usage.get("input_tokens", 0)
        out_t = usage.get("output_tokens", 0)
        total_input_tokens += in_t
        total_output_tokens += out_t

        if not response.tool_calls:
            print("Model did not request any further tool calls. Exiting tool loop.")
            break

        for tool_call in response.tool_calls:
            t_name = tool_call["name"]
            t_args = tool_call["args"]
            t_id = tool_call["id"]
            print(f" -> Model requested tool: {t_name}({t_args})")
            
            tool_func = tool_map.get(t_name)
            if tool_func:
                tool_result = tool_func.invoke(t_args)
            else:
                tool_result = f"Error: Tool {t_name} not found."

            messages.append(ToolMessage(content=str(tool_result), tool_call_id=t_id))

    # Final step: Format into structured ResearcherOutput
    print("\nFormatting gathered PRs into structured ResearcherOutput JSON...")
    structured_llm = llm.with_structured_output(ResearcherOutput, include_raw=True)
    format_prompt = (
        f"Based on the tool results above, extract ALL PRs merged between {week_start} and {week_end}.\n"
        "Ensure every entry has pr_number, title, summary, url, and merged_at.\n"
        "Exclude unmerged PRs or PRs merged outside this week."
    )
    messages.append(HumanMessage(content=format_prompt))
    
    struct_result = execute_with_retry(lambda: structured_llm.invoke(messages))
    struct_usage = getattr(struct_result["raw"], "usage_metadata", {}) or {}
    total_input_tokens += struct_usage.get("input_tokens", 0)
    total_output_tokens += struct_usage.get("output_tokens", 0)

    parsed_output: ResearcherOutput = struct_result["parsed"]
    cost = calculate_cost(total_input_tokens, total_output_tokens)

    print("\n[Structured Researcher Output]:")
    print(json.dumps(parsed_output.model_dump(), indent=2))

    print("\n[Researcher Telemetry]:")
    print(f"  Total Input Tokens:  {total_input_tokens}")
    print(f"  Total Output Tokens: {total_output_tokens}")
    print(f"  Total Tokens:        {total_input_tokens + total_output_tokens}")
    print(f"  Estimated Cost:      ${cost:.6f} USD")
    print("\nStep 2 completed successfully!\n")
    return parsed_output


if __name__ == "__main__":
    run_researcher_with_tools()
