"""
Step 1: One Call with Structured JSON Output
-------------------------------------------
Prompts Google Gemini via langchain-google-genai to extract structured JSON
(title, summary, source_url) using Pydantic and llm.with_structured_output().
Tracks input/output tokens and cost.
"""

import json
from config import get_llm, calculate_cost, execute_with_retry, GEMINI_MODEL
from models import Step1Output


def run_step_1():
    print("=" * 60)
    print("STEP 1: Single Gemini Call with Structured JSON Output")
    print(f"Model: {GEMINI_MODEL}")
    print("=" * 60)

    # Initialize low-temperature model
    llm = get_llm(temperature=0.2)
    
    # Configure structured output with raw response for token extraction
    structured_llm = llm.with_structured_output(Step1Output, include_raw=True)

    prompt = (
        "You are an expert technical release note writer.\n"
        "Summarize the following pull request into clean, user-friendly language:\n\n"
        "Repo: pallets/flask\n"
        "PR #6168: 'drop support for Python 3.10'\n"
        "Description: Python 3.10 has reached end-of-life status. We are cleaning up CI matrices, "
        "updating type annotations to modern syntax, and bumping minimum requirements to Python 3.11+.\n"
        "PR URL: https://github.com/pallets/flask/pull/6168\n\n"
        "Provide a user-friendly title, summary, and the exact source URL."
    )

    print("\nSending prompt to Gemini...")
    result = execute_with_retry(lambda: structured_llm.invoke(prompt))

    parsed: Step1Output = result["parsed"]
    raw_msg = result["raw"]
    usage = getattr(raw_msg, "usage_metadata", {}) or {}
    in_tokens = usage.get("input_tokens", 0)
    out_tokens = usage.get("output_tokens", 0)
    cost = calculate_cost(in_tokens, out_tokens)

    print("\n[Structured Output Received]:")
    print(json.dumps(parsed.model_dump(), indent=2))

    print("\n[Token & Cost Telemetry]:")
    print(f"  Input Tokens:  {in_tokens}")
    print(f"  Output Tokens: {out_tokens}")
    print(f"  Total Tokens:  {in_tokens + out_tokens}")
    print(f"  Estimated Cost: ${cost:.6f} USD")
    print("\nStep 1 completed successfully!\n")
    return parsed, usage


if __name__ == "__main__":
    run_step_1()
