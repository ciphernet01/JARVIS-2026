"""
Web tools for JARVIS agent.
Search and fetch without API keys.
"""

import logging
from typing import Dict, List

import httpx

try:
    from duckduckgo_search import DDGS
except Exception:  # pragma: no cover
    DDGS = None

logger = logging.getLogger(__name__)


def search_web(query: str) -> Dict[str, object]:
    """Search the web using DuckDuckGo (no API key needed). Returns top results."""
    logger.info(f"Tool search_web: {query}")
    if DDGS is None:
        return {
            "success": False,
            "output": "",
            "error": "duckduckgo_search package not installed",
        }
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=5)
            simplified: List[Dict[str, str]] = []
            for r in results:
                simplified.append(
                    {
                        "title": r.get("title", ""),
                        "href": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    }
                )
        return {
            "success": True,
            "output": simplified,
            "error": None,
        }
    except Exception as exc:
        logger.error(f"search_web failed: {exc}")
        return {
            "success": False,
            "output": "",
            "error": str(exc),
        }


def fetch_url(url: str) -> Dict[str, object]:
    """Fetch the text content of a URL."""
    logger.info(f"Tool fetch_url: {url}")
    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        text = resp.text
        # Limit length to avoid flooding context
        if len(text) > 10000:
            text = text[:10000] + "\n... [truncated]"
        return {
            "success": True,
            "output": text,
            "error": None,
        }
    except Exception as exc:
        logger.error(f"fetch_url failed: {exc}")
        return {
            "success": False,
            "output": "",
            "error": str(exc),
        }
