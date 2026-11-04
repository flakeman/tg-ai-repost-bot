import html
import re
from typing import List


def strip_html_tags(text: str) -> str:
    """
    Strips HTML tags and unescapes entities for fallback plain-text rendering.
    """
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    return html.unescape(clean)


def convert_markdown_to_telegram_html(text: str) -> str:
    """
    Converts markdown backticks, bold tags, and escapes invalid HTML characters
    so Telegram HTML parser does not throw 'Unsupported start tag' (e.g. on '<0,005').
    - ```lang\ncode\n``` -> <pre><code class="language-lang">code</code></pre>
    - `code` -> <code>code</code>
    - **bold** -> <b>bold</b>
    - Raw '<', '>' and unescaped '&' -> safely escaped to '&lt;', '&gt;', '&amp;'
    """
    if not text:
        return ""

    placeholders = {}
    p_counter = 0

    def add_placeholder(val: str) -> str:
        nonlocal p_counter
        key = f"\x00PH_{p_counter}\x00"
        p_counter += 1
        placeholders[key] = val
        return key

    # 1. Multi-line code blocks: ```[lang]\n...\n```
    def replace_code_block(match: re.Match) -> str:
        lang = (match.group(1) or "").strip()
        code = match.group(2).strip("\r\n")
        escaped_code = html.escape(code)
        if lang:
            block = f'<pre><code class="language-{lang}">{escaped_code}</code></pre>'
        else:
            block = f"<pre><code>{escaped_code}</code></pre>"
        return add_placeholder(block)

    text = re.sub(r"```([a-zA-Z0-9_-]*)\r?\n?(.*?)```", replace_code_block, text, flags=re.DOTALL)

    # 2. Inline code: `code`
    def replace_inline_code(match: re.Match) -> str:
        code = match.group(1)
        escaped_code = html.escape(code)
        return add_placeholder(f"<code>{escaped_code}</code>")

    text = re.sub(r"`([^`\r\n]+)`", replace_inline_code, text)

    # 3. Preserve existing valid Telegram HTML tags (if already present)
    valid_tag_pattern = re.compile(
        r"</?(?:b|strong|i|em|u|ins|s|strike|del|code|pre|blockquote|tg-spoiler)\b[^>]*>|<a\s+href=[\"'][^\"']*[\"']>|</a>",
        re.IGNORECASE,
    )

    def replace_valid_tag(match: re.Match) -> str:
        return add_placeholder(match.group(0))

    text = valid_tag_pattern.sub(replace_valid_tag, text)

    # 4. Escape remaining raw HTML characters: & < >
    # Only escape '&' if not part of an existing HTML entity
    text = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", text)
    text = text.replace("<", "&lt;").replace(">", "&gt;")

    # 5. Convert markdown bold: **text** -> <b>text</b>
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)

    # 6. Restore all placeholders in reverse order
    for key, val in reversed(list(placeholders.items())):
        text = text.replace(key, val)

    return text


def split_telegram_message(text: str, max_length: int = 4000) -> List[str]:
    """
    Splits long messages into Telegram-compliant chunks (max 4096 chars per message).
    Uses safe boundaries: double newlines, single newlines, spaces, or hard limit.
    """
    if not text:
        return [""]

    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while len(remaining) > max_length:
        cutoff = max_length

        # Try to split by paragraph boundary first
        idx = remaining.rfind("\n\n", 0, cutoff)
        if idx != -1 and idx >= max_length // 3:
            split_pos = idx
            chunks.append(remaining[:split_pos].rstrip())
            remaining = remaining[split_pos + 2:].lstrip()
            continue

        # Try to split by single line break
        idx = remaining.rfind("\n", 0, cutoff)
        if idx != -1 and idx >= max_length // 3:
            split_pos = idx
            chunks.append(remaining[:split_pos].rstrip())
            remaining = remaining[split_pos + 1:].lstrip()
            continue

        # Try to split by whitespace
        idx = remaining.rfind(" ", 0, cutoff)
        if idx != -1 and idx >= max_length // 3:
            split_pos = idx
            chunks.append(remaining[:split_pos].rstrip())
            remaining = remaining[split_pos + 1:].lstrip()
            continue

        # Hard cut if no suitable delimiter found
        chunks.append(remaining[:cutoff])
        remaining = remaining[cutoff:]

    rem = remaining.strip()
    if rem:
        chunks.append(rem)

    return chunks
