"""
Role 3: CHECKER Node
--------------------
A separate verification agent with its own prompt and temperature 0.
Tests the draft against two critical rules:
  (a) Every line maps to a real PR from the Researcher's list.
  (b) No merged PR is missing from the notes.

Returns structured JSON:
  {
    "passed": bool,
    "invented_lines": [...],
    "missing_prs": [...],
    "feedback": "..."
  }

Also executes a deterministic plain Python check (no LLM) to verify
the LLM Checker's accuracy and calculate coverage metrics.
"""

import re
import json
from typing import Dict, Any, List, Set, Tuple
from langchain_core.messages import SystemMessage, HumanMessage
from config import get_llm, calculate_cost, execute_with_retry
from models import CheckerOutput
from state import AgentState


def run_python_rule_check(draft_text: str, researcher_prs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministic Python verification (no LLM) of the two rules:
    Rule (a): Every bullet line maps to a real PR from researcher's list.
    Rule (b): No merged PR is missing from the notes.
    """
    valid_pr_map = {int(p["pr_number"]): p for p in researcher_prs}
    valid_pr_numbers = set(valid_pr_map.keys())

    invented_lines: List[str] = []
    valid_lines: List[str] = []
    mentioned_prs: Set[int] = set()

    for raw_line in draft_text.splitlines():
        line = raw_line.strip()
        # Only inspect bullet items (ignore headers like '# Release Notes', '## Features', or blank lines)
        if not (line.startswith("-") or line.startswith("*")):
            continue
        
        # Ignore placeholders like "- None in this release"
        if "none in this release" in line.lower():
            continue

        # Extract all PR numbers using regex (e.g. [#101], #101, (#101))
        matches = re.findall(r"#(\d+)", line)
        if not matches:
            # Bullet line without any PR number attribution is an invented/unmapped line
            invented_lines.append(line)
        else:
            line_has_invalid_pr = False
            for m in matches:
                pr_num = int(m)
                if pr_num not in valid_pr_numbers:
                    line_has_invalid_pr = True
                else:
                    mentioned_prs.add(pr_num)
            
            if line_has_invalid_pr:
                invented_lines.append(line)
            else:
                valid_lines.append(line)

    missing_prs = sorted(list(valid_pr_numbers - mentioned_prs))
    total_bullet_lines = len(invented_lines) + len(valid_lines)
    
    # Calculate scores
    line_accuracy_percent = (len(valid_lines) / total_bullet_lines * 100.0) if total_bullet_lines > 0 else 100.0
    pr_coverage_percent = (len(mentioned_prs) / len(valid_pr_numbers) * 100.0) if len(valid_pr_numbers) > 0 else 100.0
    passed = (len(invented_lines) == 0) and (len(missing_prs) == 0)

    return {
        "passed": passed,
        "invented_lines": invented_lines,
        "valid_lines": valid_lines,
        "missing_prs": missing_prs,
        "mentioned_prs": sorted(list(mentioned_prs)),
        "total_valid_prs": len(valid_pr_numbers),
        "line_accuracy_percent": round(line_accuracy_percent, 2),
        "pr_coverage_percent": round(pr_coverage_percent, 2),
    }


def checker_node(state: AgentState) -> Dict[str, Any]:
    print("\n" + "=" * 65)
    print("-> [ROLE 3: CHECKER] Validating Draft Quality & Integrity")
    print("=" * 65)

    draft = state.get("current_draft", "")
    researcher_prs = state.get("researcher_prs", [])
    retry_count = state.get("retry_count", 0)

    # 1. Deterministic Python Check
    py_result = run_python_rule_check(draft, researcher_prs)
    print(f"[Checker - Python Rule Check Result]:")
    print(f"  * Passed: {py_result['passed']}")
    print(f"  * Line Accuracy: {py_result['line_accuracy_percent']}% ({len(py_result['valid_lines'])} valid, {len(py_result['invented_lines'])} invented)")
    print(f"  * PR Coverage: {py_result['pr_coverage_percent']}% (Covered: {py_result['mentioned_prs']}, Missing: {py_result['missing_prs']})")

    # 2. LLM Checker (Temperature 0)
    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(CheckerOutput, include_raw=True)

    system_prompt = (
        "You are the Checker agent in an automated release note pipeline.\n"
        "Your task is to independently audit the candidate release notes against the Researcher's list of verified PRs.\n\n"
        "EVALUATION CRITERIA (both must strictly pass):\n"
        "Rule 1: EVERY bullet line in the notes must map to a real, valid PR number from the researcher list. "
        "Any bullet point referencing a nonexistent PR or lacking a PR attribution is an INVENTED LINE.\n"
        "Rule 2: NO merged PR from the researcher list may be omitted. Every PR must be documented. "
        "Any PR from the researcher list not mentioned is a MISSING PR.\n\n"
        "You must be rigorous and skeptical. If there are invented lines or missing PRs, set passed=False "
        "and provide crystal clear feedback indicating exactly what lines to delete and what PR numbers to add."
    )

    audit_prompt = (
        f"Verified Researcher Merged PRs:\n{json.dumps(researcher_prs, indent=2)}\n\n"
        f"Candidate Release Notes Draft:\n{draft}\n\n"
        "Audit the draft now. Output JSON with:\n"
        "- passed: true only if there are 0 invented lines and 0 missing PRs; false otherwise\n"
        "- invented_lines: list of strings of any invented/unattributed lines\n"
        "- missing_prs: list of integer PR numbers that were left out\n"
        "- feedback: actionable instructions for the Drafter to repair the notes"
    )

    res = execute_with_retry(lambda: structured_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=audit_prompt)
    ]))

    raw_msg = res["raw"]
    usage = getattr(raw_msg, "usage_metadata", {}) or {}
    in_tokens = usage.get("input_tokens", 0)
    out_tokens = usage.get("output_tokens", 0)
    cost = calculate_cost(in_tokens, out_tokens)

    checker_res: CheckerOutput = res["parsed"]

    # Combine LLM and Python verification (fail if either finds violations)
    final_passed = checker_res.passed and py_result["passed"]
    combined_invented = list(dict.fromkeys(checker_res.invented_lines + py_result["invented_lines"]))
    combined_missing = sorted(list(set(checker_res.missing_prs + py_result["missing_prs"])))

    print(f"\n[Checker LLM Evaluation]:")
    print(f"  * Passed: {checker_res.passed}")
    print(f"  * Invented Lines Detected: {len(combined_invented)}")
    print(f"  * Missing PR Numbers: {combined_missing}")
    print(f"  * Feedback: {checker_res.feedback}")
    print(f"[Checker Telemetry] Tokens: {in_tokens} in / {out_tokens} out | Cost: ${cost:.6f}")

    # Accumulate token usage
    token_usage = state.get("token_usage_by_agent", {})
    existing_checker = token_usage.get("Checker", {"input_tokens": 0, "output_tokens": 0})
    token_usage["Checker"] = {
        "input_tokens": existing_checker["input_tokens"] + in_tokens,
        "output_tokens": existing_checker["output_tokens"] + out_tokens,
    }

    cost_by_agent = state.get("cost_by_agent", {})
    cost_by_agent["Checker"] = cost_by_agent.get("Checker", 0.0) + cost

    rejection_history = state.get("rejection_history", [])
    new_retry_count = retry_count

    if not final_passed:
        new_retry_count += 1
        rejection_history.append({
            "attempt": new_retry_count,
            "feedback": checker_res.feedback,
            "invented_lines": combined_invented,
            "missing_prs": combined_missing,
            "python_accuracy": py_result["line_accuracy_percent"],
            "python_coverage": py_result["pr_coverage_percent"]
        })
        print(f"[Checker Action] Draft REJECTED. Retry counter incremented to {new_retry_count}.")
    else:
        print("[Checker Action] Draft PASSED all verification checks!")

    return {
        "checker_passed": final_passed,
        "checker_feedback": checker_res.feedback,
        "checker_invented_lines": combined_invented,
        "checker_missing_prs": combined_missing,
        "python_verifier_result": py_result,
        "retry_count": new_retry_count,
        "rejection_history": rejection_history,
        "token_usage_by_agent": token_usage,
        "cost_by_agent": cost_by_agent,
    }
