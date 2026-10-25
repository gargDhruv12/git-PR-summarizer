"""
Test and Score Script
---------------------
1. Loads ground-truth PRs from test_data/ground_truth_prs.json (offline test).
2. PLANTS TWO ERRORS:
   - Error 1: An invented feature line mapping to no PR (e.g. [#999] AI auto-reply).
   - Error 2: A missed breaking change PR (#103 left out).
3. Executes Checker to prove both planted errors are detected and rejected.
4. Computes quantitative scores:
   - % of lines that map to a real PR
   - % of merged PRs covered
   - Planted error detection accuracy
5. Runs the full self-checking graph pipeline to produce the final verified draft (100% coverage, 0 invented lines).
"""

import os
import sys
import json

# Ensure console supports utf-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from state import AgentState
from nodes.checker import checker_node, run_python_rule_check
from graph import app


def load_ground_truth():
    data_path = os.path.join(os.path.dirname(__file__), "test_data", "ground_truth_prs.json")
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_checker_with_planted_errors():
    print("\n" + "=" * 70)
    print("PHASE 1: TESTING CHECKER WITH PLANTED ERRORS")
    print("=" * 70)

    ground_truth = load_ground_truth()
    valid_pr_numbers = {p["pr_number"] for p in ground_truth}
    print(f"Loaded {len(ground_truth)} ground truth PRs: {sorted(list(valid_pr_numbers))}")

    # Construct draft with PLANTED ERRORS:
    # Planted Error 1: Invented feature [#999] (does not exist in ground truth)
    # Planted Error 2: PR #103 (breaking change: Remove deprecated v1 OAuth endpoints) is omitted
    faulty_draft = """# Release Notes

## Features
- [#101] Download your weekly activity reports in standard CSV spreadsheet format.
- [#105] Introduced sleek high-contrast dark theme in user settings.
- [#999] Added AI auto-reply feature to user direct messages.

## Fixes
- [#102] Fixed unexpected session timeout that logged active users out prematurely.
- [#104] Fixed email notification timestamps to respect user locale instead of UTC.

## Breaking Changes
- None in this release
"""

    print("\n[Planted Errors Introduced in Draft]:")
    print("  1. INVENTED FEATURE: '- [#999] Added AI auto-reply feature to user direct messages.' (PR #999 does not exist)")
    print("  2. MISSED BREAKING CHANGE: PR #103 ('Remove deprecated v1 OAuth endpoints') was completely left out.\n")

    print("[Faulty Candidate Draft]:")
    print(faulty_draft)

    # Initial state with faulty draft
    test_state: AgentState = {
        "repo_name": "example/analytics-app",
        "week_start": "2026-10-01",
        "week_end": "2026-10-08",
        "researcher_prs": ground_truth,
        "current_draft": faulty_draft,
        "retry_count": 0,
        "max_retries": 3,
        "token_usage_by_agent": {},
        "cost_by_agent": {},
        "rejection_history": []
    }

    print("\nRunning Checker Node on Faulty Draft...")
    checker_result = checker_node(test_state)

    # Audit the Checker's performance
    passed = checker_result["checker_passed"]
    invented = checker_result["checker_invented_lines"]
    missing = checker_result["checker_missing_prs"]
    py_check = checker_result["python_verifier_result"]

    # Verify Planted Error 1 detection
    caught_invented = any("999" in line for line in invented)
    # Verify Planted Error 2 detection
    caught_missing_103 = (103 in missing)

    print("\n" + "-" * 70)
    print("CHECKER EVALUATION ON FAULTY DRAFT:")
    print("-" * 70)
    print(f"  * Rejected Draft:               {not passed} (Passed: {passed})")
    print(f"  * Planted Error 1 Caught (#999) : {'PASSED (Caught)' if caught_invented else 'FAILED (Missed)'}")
    print(f"  * Planted Error 2 Caught (#103) : {'PASSED (Caught)' if caught_missing_103 else 'FAILED (Missed)'}")
    print(f"  * Line Accuracy Score           : {py_check['line_accuracy_percent']}%")
    print(f"  * PR Coverage Score             : {py_check['pr_coverage_percent']}%")
    print(f"  * Checker Feedback              : {checker_result['checker_feedback']}")

    assert not passed, "Checker should have REJECTED the faulty draft!"
    assert caught_invented, "Checker failed to catch invented line #999!"
    assert caught_missing_103, "Checker failed to catch missing PR #103!"

    print("\n>>> Phase 1 Success: Checker successfully caught both planted errors and rejected draft!")
    return {
        "planted_error_1_caught": caught_invented,
        "planted_error_2_caught": caught_missing_103,
        "faulty_line_accuracy": py_check["line_accuracy_percent"],
        "faulty_pr_coverage": py_check["pr_coverage_percent"],
    }


def test_full_pipeline_to_perfection():
    print("\n" + "=" * 70)
    print("PHASE 2: RUNNING FULL SELF-CHECKING PIPELINE ON TEST WEEK")
    print("=" * 70)

    ground_truth = load_ground_truth()

    initial_state: AgentState = {
        "repo_name": "example/analytics-app",
        "week_start": "2026-10-01",
        "week_end": "2026-10-08",
        "ground_truth_prs": ground_truth,
        "retry_count": 0,
        "max_retries": 3,
        "token_usage_by_agent": {},
        "cost_by_agent": {},
        "rejection_history": [],
    }

    print("Executing LangGraph agent system...")
    final_state = app.invoke(initial_state)

    final_draft = final_state.get("current_draft", "")
    prs = final_state.get("researcher_prs", [])
    py_verif = run_python_rule_check(final_draft, prs)

    line_score = py_verif["line_accuracy_percent"]
    coverage_score = py_verif["pr_coverage_percent"]
    all_mapped = (line_score == 100.0)
    none_missing = (coverage_score == 100.0)

    print("\n" + "=" * 70)
    print("FINAL QUALITY SCORECARD")
    print("=" * 70)
    print(f"Total Merged PRs in Ground Truth : {len(prs)}")
    print(f"Valid Lines in Final Notes       : {len(py_verif['valid_lines'])}")
    print(f"Invented Lines                   : {len(py_verif['invented_lines'])}")
    print(f"Missing PRs                      : {py_verif['missing_prs']}")
    print(f"Line Mapping Accuracy Score      : {line_score}%")
    print(f"Merged PR Coverage Score         : {coverage_score}%")
    print(f"Checker Status                   : {final_state.get('status')}")
    print(f"Total Retries Used               : {final_state.get('retry_count')}")
    print(f"Total Pipeline Cost (USD)        : ${final_state.get('total_cost_usd', 0.0):.6f}")

    done_condition = all_mapped and none_missing and final_state.get("status") == "PASSED"
    print("\n" + "-" * 70)
    if done_condition:
        print(">>> CRITERIA MET: 'DONE WHEN: every line maps to a PR and nothing is missing on the test week.'")
        print(">>> ALL VERIFICATION CHECKS PASSED WITH A PERFECT 100% SCORE!")
    else:
        print(">>> Pipeline finished with non-passing criteria.")
    print("-" * 70 + "\n")

    return final_state, py_verif


if __name__ == "__main__":
    faulty_metrics = test_checker_with_planted_errors()
    final_state, perfect_metrics = test_full_pipeline_to_perfection()
