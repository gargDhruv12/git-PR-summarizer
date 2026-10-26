"""
Test Suite: Evaluate All Benchmark Test Cases
---------------------------------------------
Loops over every case file in test_data/cases/, executes the Checker
rule verification, compares actual vs. expected results, prints a scorecard
table, saves the results to outputs/results.csv, and prints a final summary.
"""

import os
import sys
import json
import csv
from typing import Dict, Any

# Ensure console supports utf-8 output on all platforms
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure repo root is available in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nodes.checker import run_python_rule_check, checker_node


def run_case_checker(case_data: Dict[str, Any], use_llm: bool = False) -> Dict[str, Any]:
    """
    Executes the checker on candidate draft and ground truth PRs.
    - Default: uses deterministic Python verification from nodes.checker (fast, reproducible, offline).
    - If use_llm is True (via --llm flag): runs the full LLM-based checker node.
    """
    draft = case_data.get("candidate_draft", "")
    prs = case_data.get("merged_prs", [])

    if use_llm:
        # Construct agent state for full checker node
        state = {
            "repo_name": case_data.get("repo_name", "test/repo"),
            "week_start": case_data.get("week_start", ""),
            "week_end": case_data.get("week_end", ""),
            "researcher_prs": prs,
            "current_draft": draft,
            "retry_count": 0,
            "max_retries": 3,
            "token_usage_by_agent": {},
            "cost_by_agent": {},
            "rejection_history": [],
        }
        res = checker_node(state)
        py_result = res["python_verifier_result"]
        passed = res["checker_passed"]
    else:
        # Run deterministic rule check directly
        py_result = run_python_rule_check(draft, prs)
        passed = py_result["passed"]

    actual = "pass" if passed else "reject"
    return {
        "passed": passed,
        "actual": actual,
        "line_accuracy_percent": py_result["line_accuracy_percent"],
        "pr_coverage_percent": py_result["pr_coverage_percent"],
        "invented_lines": py_result["invented_lines"],
        "missing_prs": py_result["missing_prs"],
    }


def main():
    # Support optional --llm CLI flag to switch from deterministic check to full LLM checker node
    use_llm = "--llm" in sys.argv

    base_dir = os.path.dirname(os.path.abspath(__file__))
    cases_dir = os.path.join(base_dir, "test_data", "cases")
    outputs_dir = os.path.join(base_dir, "outputs")
    os.makedirs(outputs_dir, exist_ok=True)
    results_csv_path = os.path.join(outputs_dir, "results.csv")

    # Find and sort all case files in test_data/cases/
    case_files = sorted([f for f in os.listdir(cases_dir) if f.endswith(".json")])
    if not case_files:
        print(f"No JSON test cases found in {cases_dir}")
        return

    table_rows = []
    passed_cases_count = 0
    planted_errors_total = 0
    planted_errors_caught = 0

    # Print table header
    print("\n" + "=" * 90)
    print(f"{'Case Name':<38} {'Expected':<10} {'Actual':<10} {'Status':<10} {'Line Acc.':<11} {'PR Cov.':<10}")
    print("=" * 90)

    for fname in case_files:
        fpath = os.path.join(cases_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            case_data = json.load(f)

        expected = case_data.get("expected", "pass").lower()
        checker_out = run_case_checker(case_data, use_llm=use_llm)
        actual = checker_out["actual"]

        # Check if actual matches expectation
        test_passed = (actual == expected)
        status = "PASSED" if test_passed else "FAILED"
        if test_passed:
            passed_cases_count += 1

        # Track planted error cases
        is_planted = (expected == "reject") or ("planted" in fname)
        if is_planted:
            planted_errors_total += 1
            if actual == "reject":
                planted_errors_caught += 1

        line_acc_str = f"{checker_out['line_accuracy_percent']:.1f}%"
        pr_cov_str = f"{checker_out['pr_coverage_percent']:.1f}%"

        # Print row to console
        print(f"{fname:<38} {expected:<10} {actual:<10} {status:<10} {line_acc_str:<11} {pr_cov_str:<10}")

        table_rows.append({
            "name": fname,
            "expected": expected,
            "actual": actual,
            "passed_or_failed": status,
            "line_accuracy": line_acc_str,
            "pr_coverage": pr_cov_str,
        })

    print("-" * 90)

    # Save results table to outputs/results.csv
    fieldnames = ["name", "expected", "actual", "passed_or_failed", "line_accuracy", "pr_coverage"]
    with open(results_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(table_rows)

    # Compute summary metrics
    all_planted_caught = (planted_errors_total > 0 and planted_errors_caught == planted_errors_total)
    planted_str = "yes" if all_planted_caught else "no"
    summary_msg = f"{passed_cases_count}/{len(case_files)} cases passed; all planted errors caught: {planted_str}"

    print(f"\nFinal Summary: {summary_msg}")
    print(f"Results saved to: {results_csv_path}\n")


if __name__ == "__main__":
    main()
