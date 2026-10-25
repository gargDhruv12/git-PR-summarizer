"""
Graph State definition for the 4-agent PR summarizer system.
Tracks the repository information, PR artifacts, drafts, checker evaluations,
retry count, rejection history, per-agent token usage, and costs.
"""

from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict, total=False):
    # Repository & target date range
    repo_name: str
    week_start: str
    week_end: str
    
    # Optional ground truth for offline testing or synthetic evaluation
    ground_truth_prs: Optional[List[Dict[str, Any]]]
    
    # Researcher Output
    researcher_prs: List[Dict[str, Any]]
    
    # Drafter Output
    current_draft: str
    draft_history: List[str]
    draft_features: List[str]
    draft_fixes: List[str]
    draft_breaking_changes: List[str]
    
    # Checker Output & Evaluation
    checker_passed: bool
    checker_invented_lines: List[str]
    checker_missing_prs: List[int]
    checker_feedback: str
    
    # Plain Python verifier output (for dual-checking LLM Checker's accuracy)
    python_verifier_result: Dict[str, Any]
    
    # Loop and Retry tracking
    retry_count: int
    max_retries: int
    status: str  # "IN_PROGRESS", "PASSED", "FAILED"
    rejection_history: List[Dict[str, Any]]
    
    # Token & Cost Telemetry (tracked per agent role)
    token_usage_by_agent: Dict[str, Dict[str, int]]
    cost_by_agent: Dict[str, float]
    total_tokens: Dict[str, int]
    total_cost_usd: float
    
    # Reporter Output
    reporter_summary: str
    open_doubts: List[str]
