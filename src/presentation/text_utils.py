from typing import List


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
