import re
from typing import Tuple
from bs4 import BeautifulSoup
import httpx
import trafilatura
from src.domain.interfaces import IArticleExtractor


class ExtractionError(Exception):
    """Raised when an article cannot be extracted or downloaded."""
    pass


class TrafilaturaExtractor(IArticleExtractor):
    def __init__(self, timeout_sec: float = 15.0):
        self.timeout_sec = timeout_sec
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    async def extract(self, url: str) -> Tuple[str, str]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec, follow_redirects=True, headers=self.headers) as client:
                response = await client.get(url)
                if response.status_code >= 400:
                    raise ExtractionError(f"HTTP error {response.status_code} while fetching {url}")
                html = response.text
        except httpx.RequestError as exc:
            raise ExtractionError(f"Network error requesting {url}: {exc}") from exc

        # 1. Primary extraction via trafilatura
        body = trafilatura.extract(
            html,
            include_links=False,
            include_images=False,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )
        
        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata and metadata.title else ""

        # 2. Fallback to BeautifulSoup if body or title missing
        if not body or len(body.strip()) < 50 or not title:
            soup = BeautifulSoup(html, "html.parser")

            if not title:
                # Try OpenGraph, H1, or <title>
                og_title = soup.find("meta", property="og:title")
                h1 = soup.find("h1")
                if og_title and og_title.get("content"):
                    title = og_title["content"].strip()
                elif h1:
                    title = h1.get_text(strip=True)
                elif soup.title:
                    title = soup.title.get_text(strip=True)

            if not body or len(body.strip()) < 50:
                # Remove unwanted tags
                for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
                    tag.decompose()

                article_node = soup.find("article") or soup.find("main") or soup.find("body")
                if article_node:
                    paragraphs = [p.get_text(strip=True) for p in article_node.find_all("p")]
                    body = "\n\n".join([p for p in paragraphs if len(p) > 20])

        title = title.strip() if title else "Без заголовка"
        body = body.strip() if body else ""

        if not body or len(body) < 30:
            raise ExtractionError("Unable to extract meaningful article content from the URL")

        # Clean multiple empty lines
        body = re.sub(r"\n{3,}", "\n\n", body)

        return title, body
