"""
Tools for Researcher Agent:
1. GitHub Pull Request search/list tool via GitHub REST API.
2. Web page / PR fetch tool.
"""

import json
import os
import requests
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from config import GITHUB_TOKEN


def _get_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "git-pr-summarizer/1.0",
    }
    token = os.getenv("GITHUB_TOKEN", GITHUB_TOKEN)
    if token and token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    return headers


@tool
def fetch_github_prs(repo: str, limit: int = 15) -> str:
    """
    Fetches closed/merged pull requests from a public GitHub repository.
    Args:
        repo: Repository in the format 'owner/repo' (e.g. 'pallets/flask').
        limit: Number of recent closed PRs to inspect (default 15).
    Returns:
        JSON string listing pull requests with number, title, body snippet, html_url, and merged_at.
    """
    url = f"https://api.github.com/repos/{repo}/pulls?state=closed&per_page={min(limit, 100)}&sort=updated&direction=desc"
    try:
        response = requests.get(url, headers=_get_headers(), timeout=15)
        if response.status_code == 403 and "rate limit" in response.text.lower():
            return json.dumps({
                "error": "GitHub API rate limit exceeded. Set GITHUB_TOKEN in .env to increase limit."
            })
        if response.status_code != 200:
            return json.dumps({
                "error": f"GitHub API error {response.status_code}: {response.text[:300]}"
            })
        
        data = response.json()
        simplified_prs = []
        for pr in data:
            simplified_prs.append({
                "number": pr.get("number"),
                "title": pr.get("title"),
                "merged_at": pr.get("merged_at"),
                "html_url": pr.get("html_url"),
                "body_snippet": (pr.get("body") or "")[:250],
            })
        return json.dumps(simplified_prs, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch GitHub PRs: {str(e)}"})


@tool
def fetch_web_page(url: str) -> str:
    """
    Fetches content from a URL (e.g., PR detail page, commit patch, or doc).
    Args:
        url: The web URL to fetch.
    Returns:
        Text content from the page (truncated to avoid context overflow).
    """
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "git-pr-summarizer/1.0"},
            timeout=15
        )
        if response.status_code != 200:
            return f"Error fetching URL ({response.status_code}): {response.text[:200]}"
        text = response.text
        # Truncate to first 2500 chars to conserve LLM context tokens
        return text[:2500] if len(text) > 2500 else text
    except Exception as e:
        return f"Exception while fetching page: {str(e)}"


# Export tools list
ALL_TOOLS = [fetch_github_prs, fetch_web_page]
