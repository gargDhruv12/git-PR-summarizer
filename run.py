"""
Git PR Summarizer - CLI Run Script
-----------------------------------
Executes the 4-agent LangGraph pipeline:
  Researcher -> Drafter <-> Checker -> Reporter

Usage:
  python run.py --repo pallets/flask --week-start 2026-10-01
  python run.py --test
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta

# Ensure console supports utf-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from graph import app
from state import AgentState
from config import GEMINI_MODEL, MAX_RETRIES


def parse_args():
    parser = argparse.ArgumentParser(description="Generate AI release notes from GitHub PRs using LangGraph & Gemini")
    parser.add_argument(
        "--repo",
        type=str,
        default="pallets/flask",
        help="Target public GitHub repo (owner/repo), e.g. pallets/flask"
    )
    parser.add_argument(
        "--week-start",
        type=str,
        default="2026-10-01",
        help="Start date for the week (YYYY-MM-DD), e.g. 2026-10-01"
    )
    parser.add_argument(
        "--week-end",
        type=str,
        default=None,
        help="End date for the week (YYYY-MM-DD). Defaults to 7 days after week-start"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run using offline ground truth test PRs instead of live GitHub API"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Calculate week_end if not provided
    if args.week_end:
        week_end = args.week_end
    else:
        try:
            start_dt = datetime.strptime(args.week_start, "%Y-%m-%d")
            week_end = (start_dt + timedelta(days=7)).strftime("%Y-%m-%d")
        except Exception:
            week_end = args.week_start

    print("=" * 70)
    print("             GIT PR SUMMARIZER - AGENTIC RELEASE NOTES")
    print("=" * 70)
    print(f"Target Repo : {args.repo}")
    print(f"Time Window : {args.week_start} to {week_end}")
    print(f"Gemini Model: {GEMINI_MODEL}")
    print(f"Mode        : {'OFFLINE TEST' if args.test else 'LIVE GITHUB'}")
    print("=" * 70)

    ground_truth = None
    if args.test:
        test_file = os.path.join(os.path.dirname(__file__), "test_data", "ground_truth_prs.json")
        with open(test_file, "r", encoding="utf-8") as f:
            ground_truth = json.load(f)
        print(f"Loaded {len(ground_truth)} mock PRs from {test_file}")

    initial_state: AgentState = {
        "repo_name": args.repo,
        "week_start": args.week_start,
        "week_end": week_end,
        "ground_truth_prs": ground_truth,
        "retry_count": 0,
        "max_retries": MAX_RETRIES,
        "token_usage_by_agent": {},
        "cost_by_agent": {},
        "rejection_history": [],
    }

    print("\nStarting LangGraph workflow execution...")
    final_state = app.invoke(initial_state)

    print("\nWorkflow complete!")
    print(f"Overall Status: {final_state.get('status')}")
    print(f"Retries Used  : {final_state.get('retry_count')}")
    print(f"Total Cost    : ${final_state.get('total_cost_usd', 0.0):.6f}")

    # Print final release notes
    print("\n" + "=" * 70)
    print("FINAL RELEASE NOTES")
    print("=" * 70)
    print(final_state.get("current_draft", "No draft available."))

    # Print reporter's summary
    print("\n" + "=" * 70)
    print("REPORTER'S EXECUTIVE SUMMARY")
    print("=" * 70)
    print(final_state.get("reporter_summary", "No summary available."))


if __name__ == "__main__":
    main()
