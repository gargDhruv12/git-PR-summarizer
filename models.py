from typing import List, Optional
from pydantic import BaseModel, Field


# -------------------------------------------------------------
# STEP 1: Basic Structured Output Model
# -------------------------------------------------------------
class Step1Output(BaseModel):
    """Structured response model for Step 1 single-call demonstration."""
    title: str = Field(description="Clear and concise title of the change or document")
    summary: str = Field(description="Summary of changes in plain, user-friendly language")
    source_url: str = Field(description="Source URL or repository link associated with the changes")


# -------------------------------------------------------------
# ROLE 1: Researcher Models
# -------------------------------------------------------------
class PRInfo(BaseModel):
    """Information for a single merged pull request."""
    pr_number: int = Field(description="The GitHub pull request number (e.g. 101)")
    title: str = Field(description="Title of the pull request")
    summary: str = Field(description="Concise description of what this PR introduces, fixes, or changes")
    url: str = Field(description="Direct URL to the pull request on GitHub")
    merged_at: str = Field(description="ISO 8601 timestamp when the PR was merged")


class ResearcherOutput(BaseModel):
    """List of all PRs merged within the specified week."""
    prs: List[PRInfo] = Field(default_factory=list, description="List of pull requests merged within the date window")


# -------------------------------------------------------------
# ROLE 2: Drafter Models
# -------------------------------------------------------------
class ReleaseNotesDraft(BaseModel):
    """Release notes draft organized into three required sections with PR numbers on every line."""
    features: List[str] = Field(
        default_factory=list,
        description="List of feature bullet lines. Each line MUST explicitly contain its PR number, e.g. '- [#101] Added dark mode toggle'"
    )
    fixes: List[str] = Field(
        default_factory=list,
        description="List of bug fix bullet lines. Each line MUST explicitly contain its PR number, e.g. '- [#102] Fixed crash on checkout'"
    )
    breaking_changes: List[str] = Field(
        default_factory=list,
        description="List of breaking change bullet lines. Each line MUST explicitly contain its PR number, e.g. '- [#103] Removed deprecated v1 auth API'"
    )
    raw_markdown: Optional[str] = Field(
        default=None,
        description="Full markdown document rendering the release notes with sections and bullet points"
    )


# -------------------------------------------------------------
# ROLE 3: Checker Models
# -------------------------------------------------------------
class CheckerOutput(BaseModel):
    """Output from the Checker verifying the draft against ground truth PRs."""
    passed: bool = Field(
        description="True if both rules pass (all lines map to valid PRs and no merged PR is missing); False otherwise"
    )
    invented_lines: List[str] = Field(
        default_factory=list,
        description="List of lines in the draft that mention a PR not present in the researcher's list or have hallucinated claims"
    )
    missing_prs: List[int] = Field(
        default_factory=list,
        description="List of PR numbers from the researcher list that are completely omitted from the draft"
    )
    feedback: str = Field(
        description="Detailed, actionable feedback explaining why the draft passed or failed and what to fix"
    )
