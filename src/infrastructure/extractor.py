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
        title, body, _ = await self.extract_with_url(url)
        return title, body

    async def extract_with_url(self, url: str) -> Tuple[str, str, str]:
        url = url.strip()
        # Ensure url does not contain trailing whitespace or newlines
        if any(c in url for c in " \t\r\n"):
            for part in url.split():
                if part.startswith("http://") or part.startswith("https://"):
                    url = part.strip()
                    break

        # Handle Telegram post links: e.g. https://t.me/channel/123
        tg_match = re.search(r"t\.me/([^/]+)/(\d+)", url)
        if tg_match and tg_match.group(1).lower() not in ("joinchat", "addstickers", "c"):
            channel, msg_id = tg_match.group(1), tg_match.group(2)
            embed_url = f"https://t.me/{channel}/{msg_id}?embed=1"
            direct_url = f"https://t.me/{channel}/{msg_id}"
            try:
                async with httpx.AsyncClient(timeout=self.timeout_sec, follow_redirects=True, headers=self.headers) as client:
                    resp = await client.get(embed_url)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        msg_node = soup.find(class_="tgme_widget_message_text")
                        if msg_node:
                            # Check for external source links inside the telegram message
                            for a in msg_node.find_all("a", href=True):
                                href = a["href"].strip()
                                if href.startswith("http") and not any(d in href.lower() for d in ["t.me/", "telegram.org", "telegram.me"]):
                                    # Follow and extract primary article source!
                                    return await self.extract_with_url(href)

                            # If no external link found, use the telegram post text directly
                            post_text = msg_node.get_text("\n", strip=True)
                            lines = [ln.strip() for ln in post_text.split("\n") if ln.strip()]
                            title = lines[0][:80] if lines else "Новость из Telegram"
                            return title, post_text, url

                    # Fallback for video/media/unsupported posts where embed=1 does not show tgme_widget_message_text
                    resp_direct = await client.get(direct_url)
                    if resp_direct.status_code == 200:
                        soup_direct = BeautifulSoup(resp_direct.text, "html.parser")
                        og_desc = soup_direct.find("meta", property="og:description") or soup_direct.find("meta", attrs={"name": "twitter:description"})
                        if og_desc and og_desc.get("content"):
                            post_text = og_desc["content"].strip()
                            if len(post_text) > 10:
                                # Check if post_text contains an external link to extract
                                link_match = re.search(r"https?://[^\s]+", post_text)
                                if link_match:
                                    ext_link = link_match.group(0).rstrip(".,;!?)")
                                    if not any(d in ext_link.lower() for d in ["t.me/", "telegram.org", "telegram.me"]):
                                        try:
                                            return await self.extract_with_url(ext_link)
                                        except Exception:
                                            pass
                                lines = [ln.strip() for ln in post_text.split("\n") if ln.strip()]
                                og_title = soup_direct.find("meta", property="og:title")
                                title = lines[0][:80] if lines else (og_title["content"] if og_title else "Новость из Telegram")
                                return title, post_text, url
            except Exception:
                pass  # Fallback to normal URL fetching

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec, follow_redirects=True, headers=self.headers) as client:
                response = await client.get(url)
                if response.status_code >= 400:
                    raise ExtractionError(f"HTTP error {response.status_code} while fetching {url}")
                html = response.text
                final_url = str(response.url)
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

        return title, body, final_url
