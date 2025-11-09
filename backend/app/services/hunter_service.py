"""Hunter.io API integration for email discovery"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class HunterService:
    """Hunter.io API client for email discovery"""

    def __init__(self):
        self.api_key = os.getenv("HUNTER_API_KEY")
        self.base_url = "https://api.hunter.io/v2"
        self.timeout = 10  # seconds

        if not self.api_key:
            logger.warning("HUNTER_API_KEY not set - Hunter.io email discovery disabled")
