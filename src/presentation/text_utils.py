import re
from typing import List


def convert_markdown_to_telegram_html(text: str) -> str:
    """
    Converts markdown backticks and bold tags to Telegram-compliant HTML tags:
    - ```lang\ncode\n``` -> <pre><code class="language-lang">code</code></pre>
    - `code` -> <code>code</code>
    - **bold** -> <b>bold</b>
    """
    if not text:
        return ""

    # 1. Multi-line code blocks: ```[lang]\n...\n```
    def replace_code_block(match: re.Match) -> str:
        lang = (match.group(1) or "").strip()
        code = match.group(2).strip("\r\n")
        # Escape HTML entities inside code block
        code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if lang:
            return f'<pre><code class="language-{lang}">{code}</code></pre>'
        return f"<pre><code>{code}</code></pre>"

    text = re.sub(r"```([a-zA-Z0-9_-]*)\r?\n?(.*?)```", replace_code_block, text, flags=re.DOTALL)

    # 2. Inline code: `code`
    def replace_inline_code(match: re.Match) -> str:
        code = match.group(1)
        code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<code>{code}</code>"

    text = re.sub(r"`([^`\r\n]+)`", replace_inline_code, text)

    # 3. Bold: **text**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)

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
