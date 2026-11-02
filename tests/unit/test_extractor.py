import pytest
import httpx
from src.infrastructure.extractor import TrafilaturaExtractor, ExtractionError


HTML_SAMPLE_GOOD = """
<!DOCTYPE html>
<html>
<head>
    <title>OpenAI Releases New Voice Mode</title>
    <meta property="og:title" content="OpenAI Releases Advanced Voice Mode for Everyone" />
</head>
<body>
    <header><nav><a href="/">Home</a></nav></header>
    <article>
        <h1>OpenAI Releases Advanced Voice Mode for Everyone</h1>
        <p>OpenAI has officially launched its Advanced Voice Mode for all subscribers across mobile and desktop apps.</p>
        <p>The feature brings conversational latency down to 320 milliseconds and supports natural emotional inflection.</p>
    </article>
    <footer><p>© 2026 Tech News</p></footer>
</body>
</html>
"""

HTML_SAMPLE_FALLBACK = """
<!DOCTYPE html>
<html>
<head><title>Fallback Tech News</title></head>
<body>
    <h1>Breaking Tech Innovation</h1>
    <div class="content">
        <p>Researchers today announced a significant milestone in quantum error correction.</p>
        <p>The fidelity reached 99.99 percent across 100 logical qubits in tests.</p>
    </div>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_extract_trafilatura_success(monkeypatch):
    extractor = TrafilaturaExtractor()

    async def mock_get(*args, **kwargs):
        return httpx.Response(200, text=HTML_SAMPLE_GOOD, request=httpx.Request("GET", "https://news.com/1"))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    title, body = await extractor.extract("https://news.com/1")
    assert "OpenAI Releases" in title
    assert "Advanced Voice Mode" in body
    assert "320 milliseconds" in body


@pytest.mark.asyncio
async def test_extract_fallback_beautifulsoup(monkeypatch):
    extractor = TrafilaturaExtractor()

    async def mock_get(*args, **kwargs):
        return httpx.Response(200, text=HTML_SAMPLE_FALLBACK, request=httpx.Request("GET", "https://tech.com/2"))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    title, body = await extractor.extract("https://tech.com/2")
    assert "Breaking Tech Innovation" in title or "Fallback Tech News" in title
    assert "quantum error correction" in body


@pytest.mark.asyncio
async def test_extract_http_error(monkeypatch):
    extractor = TrafilaturaExtractor()

    async def mock_get(*args, **kwargs):
        return httpx.Response(404, request=httpx.Request("GET", "https://news.com/missing"))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    with pytest.raises(ExtractionError, match="HTTP error"):
        await extractor.extract("https://news.com/missing")


@pytest.mark.asyncio
async def test_extract_telegram_post_resolves_external_link(monkeypatch):
    extractor = TrafilaturaExtractor()

    tg_embed_html = """
    <!DOCTYPE html>
    <html><body>
        <div class="tgme_widget_message_text">
            Интересная новость из мира ИИ: подробнее читайте по ссылке
            <a href="https://habr.com/ru/articles/123456/">https://habr.com/ru/articles/123456/</a>
        </div>
    </body></html>
    """

    habr_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Полная статья на Хабре</title></head>
    <body>
        <article>
            <h1>Полная статья на Хабре о технологиях</h1>
            <p>Это подробный текст статьи первоисточника, опубликованный на Хабре.</p>
            <p>В тексте содержится детальное описание архитектуры и результатов тестирования.</p>
        </article>
    </body>
    </html>
    """

    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        if "embed=1" in url_str:
            return httpx.Response(200, text=tg_embed_html, request=httpx.Request("GET", url_str))
        return httpx.Response(200, text=habr_html, request=httpx.Request("GET", url_str))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    title, body = await extractor.extract("https://t.me/mychannel/777")
    assert "Хабре" in title
    assert "первоисточника" in body
