# Git PR Summarizer: Self-Checking Agentic Release Notes

An autonomous, self-auditing multi-agent system built with **LangChain**, **LangGraph**, and **Google Gemini** (`ChatGoogleGenerativeAI`). It turns one week of pull requests from any public GitHub repository into plain-language release notes that everyday users can understand, rigorously verified by a dedicated audit agent and scored with quantitative quality metrics.

---

## Architecture & System Design

```
                     ┌──────────────────┐
                     │   START NODE     │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │ 1. RESEARCHER    │◄─── GitHub REST API & Page Fetch Tools
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
           ┌────────►│ 2. DRAFTER       │
           │         └────────┬─────────┘
           │                  │
    Reject │ Feedback         ▼
    (<= 3) │         ┌──────────────────┐
           └─────────┤ 3. CHECKER       │◄─── Dual Verification: LLM (Temp 0)
                     └────────┬─────────┘      + Deterministic Python Rule Check
                              │
               Pass OR Max    │
               Retries Reached│
                              ▼
                     ┌──────────────────┐
                     │ 4. REPORTER      │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │    END NODE      │
                     └──────────────────┘
```

### The Four Specialized Roles

1. **Researcher Agent**
   - Discovers pull requests using bound tools: `fetch_github_prs` (GitHub REST API) and `fetch_web_page`.
   - Filters strictly by `merged_at` timestamp within the designated week dates.
   - Outputs structured Pydantic JSON: `{pr_number, title, summary, url, merged_at}`.

2. **Drafter Agent**
   - Organizes notes into three mandatory sections: **Features**, **Fixes**, and **Breaking Changes**.
   - Translates developer jargon into plain, user-friendly language.
   - **Mandatory Attribution**: Every bullet line MUST explicitly include its source PR number (e.g., `- [#101] Added CSV export...`).
   - Executes a two-step refinement process: writes the initial draft, then polishes it.
   - In case of Checker rejection, ingests actionable feedback to remove invented claims and incorporate omitted PRs.

3. **Checker Agent (Evaluator)**
   - Operates with its own isolated prompt and `temperature=0.0`.
   - Audits the draft against two non-negotiable rules:
     - **Rule A (No Hallucinations)**: Every bullet line must map to a real PR from the Researcher's list.
     - **Rule B (No Omissions)**: Every merged PR must be represented in the notes.
   - Outputs structured JSON: `{passed: bool, invented_lines: [], missing_prs: [], feedback: "..."}`.
   - **Dual Verification**: Executes a deterministic plain-Python verification algorithm alongside the LLM audit to guarantee 100% mathematical certainty.

4. **Reporter Agent**
   - Generates an executive run report detailing agent actions and quality audits.
   - Details any draft rejections and corrective actions.
   - Formats a comprehensive per-agent token and cost telemetry table.
   - Highlights "Open Doubts" (subtle ambiguities, migration caveats, versioning details).
   - Outputs the final verified release notes.

---

## Evaluator-Optimizer & Retries

- **Evaluator-Optimizer Loop**: If the Checker rejects the draft, the workflow loops back to the Drafter with explicit feedback.
- **Circuit Breaker**: The graph state tracks `retry_count`. A maximum of **3 retries** is allowed. If retries are exhausted, the graph routes to the Reporter with status `FAILED` to prevent infinite loops.

---

## Telemetry & Cost Tracking

- Extracts exact `input_tokens` and `output_tokens` from `response.usage_metadata` after every LLM call.
- Aggregates usage per agent role (`Researcher`, `Drafter`, `Checker`, `Reporter`) and calculates USD cost using a configurable pricing table in `config.py`.

| Agent Role  | Input Tokens | Output Tokens | Total Tokens | Estimated Cost (USD) |
|-------------|--------------|---------------|--------------|----------------------|
| Researcher  | 25,651       | 4,034         | 29,685       | $0.003134            |
| Drafter     | 799          | 740           | 1,539        | $0.000282            |
| Checker     | 468          | 401           | 869          | $0.000155            |
| Reporter    | 226          | 935           | 1,161        | $0.000297            |
| **TOTAL**   | **27,144**   | **6,110**     | **33,254**   | **$0.003868**        |

---

## Project Structure

```
git-PR-summarizer/
│
├── .env                          # Local API keys and model configuration
├── .env.example                  # Template configuration file
├── requirements.txt              # Required dependencies
├── config.py                     # LLM setup, pricing tables, rate-limit retries
├── models.py                     # Pydantic structured output models
├── state.py                      # LangGraph AgentState schema
├── tools.py                      # GitHub REST API and page-fetch tools
│
├── nodes/
│   ├── __init__.py               # Node registry
│   ├── researcher.py             # Role 1: Tool-using PR discovery agent
│   ├── drafter.py                # Role 2: Release notes drafter & refiner
│   ├── checker.py                # Role 3: Dual-verifier audit agent (Temp 0)
│   └── reporter.py               # Role 4: Telemetry and summary reporter
│
├── graph.py                      # LangGraph StateGraph & conditional edge routing
├── run.py                        # CLI runner for live repos or offline test
├── test_checker_and_score.py     # Planted error evaluation & scoring script
│
├── step1_single_call.py          # Step 1: Structured JSON single call test
├── step2_researcher_tools.py     # Step 2: Bound tools execution test
│
└── test_data/
    └── ground_truth_prs.json     # Ground truth PRs for offline scoring
```

---

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd git-PR-summarizer
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Edit or create `.env` in the project root:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-3.8-flash
   GITHUB_TOKEN=
   ```
   > **Note on Changing the Gemini Model**:
   > To switch models, change the `GEMINI_MODEL` variable in `.env`. Supported options include:
   > - `gemini-3.8-flash` (Default fast & capable recommended model)
   > - `gemini-1.5-pro` (For higher reasoning capacity)
   >
   > You can also adjust pricing definitions in `config.py` under `PRICING_PER_1M`.

---

## Running the Three Build Steps

The project was engineered and verified in three progressive milestones:

### Step 1: Single Call with Structured Output
Prompts Gemini and validates structured JSON output with Pydantic:
```bash
python step1_single_call.py
```

### Step 2: Bound Tools (GitHub API & Page Fetch)
Demonstrates Gemini autonomously calling tools to collect and filter PRs:
```bash
python step2_researcher_tools.py
```

### Step 3: Full Multi-Agent Graph Execution
Runs the complete LangGraph pipeline on live GitHub data:
```bash
python run.py --repo pallets/flask --week-start 2026-10-01
```

---

## Testing & Score Verification

To prove that the Checker reliably prevents hallucinations and omissions, run the automated test suite:

```bash
python test_checker_and_score.py
```

### What the Test Suite Evaluates

1. **Phase 1: Planted Errors Test**:
   - The test loads ground truth PRs from `test_data/ground_truth_prs.json`.
   - It deliberately plants two synthetic defects into a candidate draft:
     - **Planted Error 1**: An invented feature line `[#999] Added AI auto-reply...` mapping to no known PR.
     - **Planted Error 2**: A missed breaking change PR (`PR #103: Remove deprecated v1 OAuth endpoints`) completely omitted.
   - The Checker evaluates the draft and **must catch both errors** and reject the draft.

2. **Phase 2: Self-Correction Pipeline to Perfection**:
   - The test executes the full LangGraph graph.
   - Computes quantitative quality scores:
     - **Line Mapping Accuracy Score**: `(Valid Lines / Total Lines) * 100` (Target: 100%)
     - **Merged PR Coverage Score**: `(Covered PRs / Total PRs) * 100` (Target: 100%)
     - **Status**: PASSED

### Sample Scorecard Output

```
======================================================================
FINAL QUALITY SCORECARD
======================================================================
Total Merged PRs in Ground Truth : 5
Valid Lines in Final Notes       : 5
Invented Lines                   : 0
Missing PRs                      : []
Line Mapping Accuracy Score      : 100.0%
Merged PR Coverage Score         : 100.0%
Checker Status                   : PASSED
Total Retries Used               : 0
Total Pipeline Cost (USD)        : $0.000492

----------------------------------------------------------------------
>>> CRITERIA MET: 'DONE WHEN: every line maps to a PR and nothing is missing on the test week.'
>>> ALL VERIFICATION CHECKS PASSED WITH A PERFECT 100% SCORE!
----------------------------------------------------------------------
```

---

## CLI Options

```bash
# Run on a live public GitHub repository
python run.py --repo pallets/flask --week-start 2026-10-01

# Run on a specific custom date window
python run.py --repo facebook/react --week-start 2026-09-01 --week-end 2026-09-08

# Run in offline test mode using ground-truth dataset
python run.py --test
```
