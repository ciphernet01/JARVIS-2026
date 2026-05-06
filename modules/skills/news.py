"""
News Skill for JARVIS
Fetches top headlines from global news sources.
"""

import logging
import requests
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
from .base import Skill

logger = logging.getLogger(__name__)

class NewsSkill(Skill):
    """Fetch top global news headlines"""

    def __init__(self):
        super().__init__("news_skill", "1.0")
        self.rss_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"

    @property
    def keywords(self) -> List[str]:
        return ["news", "headlines", "what's happening", "world events", "is anything happening"]

    @property
    def description(self) -> str:
        return "Fetches top global news headlines from Google News"

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        try:
            logger.info("Fetching news headlines...")
            resp = requests.get(self.rss_url, timeout=10)
            if resp.status_code != 200:
                return "I'm sorry Sir, I'm unable to reach the news servers at the moment."

            root = ET.fromstring(resp.content)
            items = root.findall('.//item')
            
            if not items:
                return "There are no major news reports appearing on the feed right now."

            headlines = []
            for item in items[:5]:
                title = item.find('title').text
                # Remove source trailing title like " - BBC News"
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0]
                headlines.append(title)

            response = "Here are the top headlines I've gathered: " + "; ".join(headlines) + "."
            logger.info(f"News query executed: {len(headlines)} headlines found.")
            return response

        except Exception as e:
            logger.error(f"News skill error: {e}")
            return "I encountered an error while synthesizing the global feed."
