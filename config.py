import os
import time
from typing import Dict, Any, Callable
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables from .env file
load_dotenv()

# Gemini configuration
DEFAULT_MODEL = "gemini-3.5-flash"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Price table per 1,000,000 tokens (USD)
PRICING_PER_1M: Dict[str, Dict[str, float]] = {
    "gemini-3.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-3.8-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
}

# Max retry attempts for checker rejection loop
MAX_RETRIES = 3


def calculate_cost(input_tokens: int, output_tokens: int, model_name: str = GEMINI_MODEL) -> float:
    """Calculate the estimated USD cost based on token counts and model pricing."""
    pricing = PRICING_PER_1M.get(model_name, PRICING_PER_1M.get(DEFAULT_MODEL, {"input": 0.075, "output": 0.30}))
    cost_in = (input_tokens / 1_000_000.0) * pricing["input"]
    cost_out = (output_tokens / 1_000_000.0) * pricing["output"]
    return round(cost_in + cost_out, 6)


def execute_with_retry(func: Callable, max_attempts: int = 4, backoff_seconds: float = 3.0) -> Any:
    """
    Executes an LLM callable with simple retry and wait if rate-limited (HTTP 429 / ResourceExhausted)
    or upon transient network connection glitches (e.g. DNS or ConnectError).
    """
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception as e:
            err_str = str(e).lower()
            # Catch Gemini rate limit indicators or transient connection blips
            is_rate_limit = any(term in err_str for term in ["429", "resourceexhausted", "quota", "rate limit", "too many requests"])
            is_network_blip = any(term in err_str for term in ["getaddrinfo", "connecterror", "connection reset", "timed out", "timeout"])
            
            if is_rate_limit or is_network_blip:
                last_err = e
                sleep_time = backoff_seconds * attempt
                reason = "Rate-Limit" if is_rate_limit else "Network Blip"
                print(f"[{reason} Detected] Attempt {attempt}/{max_attempts}. Sleeping for {sleep_time:.1f}s before retry...")
                time.sleep(sleep_time)
            else:
                # Non-recoverable exception; re-raise immediately
                raise e
    if last_err:
        raise last_err


def get_llm(temperature: float = 0.2, model_name: str = None) -> ChatGoogleGenerativeAI:
    """
    Factory function to initialize ChatGoogleGenerativeAI.
    Uses temperature 0 for Checker and low temperature for other roles.
    """
    selected_model = model_name or GEMINI_MODEL
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not set. Please set it in your .env file.")
    
    return ChatGoogleGenerativeAI(
        model=selected_model,
        google_api_key=GOOGLE_API_KEY,
        temperature=temperature,
    )
