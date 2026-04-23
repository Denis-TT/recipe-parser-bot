import logging
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class RecipeParser:
    """Fetches and extracts clean text from recipe pages."""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    async def parse_recipe(self, url: str) -> str:
        session = await self._get_session()

        try:
            async with session.get(url, timeout=30) as response:
                response.raise_for_status()
                html = await response.text()
        except Exception as error:
            logger.error("Failed to fetch recipe page: %s", error, exc_info=True)
            raise RuntimeError(f"Failed to fetch recipe page: {error}") from error

        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        normalized = "\n".join(lines)[:50000]
        logger.info("Extracted %s characters from %s", len(normalized), url)
        return normalized

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
