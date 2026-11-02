# ADR-010: Unified Photo and Caption Message Format

## Status
Accepted

## Context
In Telegram, a standard channel post featuring an image displays the image and the article text together in a single unified message bubble (the photo acts as the media, and the text acts as the caption). 

Previously, when the generated text or draft exceeded Telegram's photo caption limit (1024 characters), the system split the post into two separate messages:
1. Message 1: The standalone image.
2. Message 2: The standalone text message with the body and buttons.

The user required that the image must NOT be sent as an isolated message, but as a single unified message containing the photo, the formatted post text (Title, Body, Source Link, Hashtags), and the approval buttons.

## Decision
1. **Prompt Constraint**: Instruct the LLM in `build_system_prompt` that the post is published directly as a photo caption in a single message. Constrain `body` to 400–700 characters (max 750 characters total), ensuring concise, high-density reporting without verbosity.
2. **Deterministic Length Safeguard in `PostContent.render_post`**:
   - `render_post(max_length: Optional[int] = None)` calculates header, source link, and hashtag overhead.
   - If total length exceeds `max_length` (1024 for photo captions), it cleanly truncates `body` at sentence or word boundaries, guaranteeing the output never exceeds 1024 characters.
3. **Draft Preview (`send_draft_preview`)**:
   - Sends the photo, rendered post caption, and inline approval keyboard (`reply_markup=kb`) together via `bot.send_photo` as a **single unified message bubble**.
   - If image prompt concept ideas exist, they are sent as a secondary supplementary note below the main post, leaving the main post 100% clean and ready for publication.
4. **Channel Publishing (`publish_to_channel`)**:
   - Publishes to the channel as a single unified `send_photo` message with `caption=draft.render_post(max_length=1024)`.

## Consequences
- The publication preview and the final channel publication are perfectly formatted as a single unified message bubble.
- Adheres strictly to Telegram Bot API's 1024-character caption limitation.
