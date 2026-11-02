# ADR-009: Telegram Message Length Safeguards and Chunking

## Status
Accepted

## Context
When long articles (e.g. from Habr via Telegram embedded posts) were processed, the LLM generated long summaries. When rendered alongside title, source link, hashtags, and 4 cover visual concept proposals, the text easily exceeded 4096 characters (Telegram's message limit) or 1024 characters (Telegram's photo caption limit).

Previously:
- In `send_draft_preview`, if `len(full_text) > 1024`, the bot sent the photo first, and then called `bot.send_message(chat_id, text=full_text, reply_markup=kb)`.
- If `len(full_text) > 4096`, `bot.send_message` crashed with `TelegramBadRequest: Bad Request: message is too long`.
- The user received only the generated image, while the drafted text, concept prompts, and interactive keyboard (`🚀 Опубликовать`, etc.) failed to be delivered.
- A similar crash would occur in `TelegramPublisher.publish_to_channel` if post text exceeded 4096 characters.

## Decision
1. **Message Chunking Utility**: Introduce `split_telegram_message(text: str, max_length: int = 4000) -> List[str]` in `src.presentation.text_utils`.
   - Chunks are split cleanly along paragraph breaks (`\n\n`), line breaks (`\n`), or whitespace.
   - Strip edge whitespace to maintain neat Telegram message formatting.
2. **Draft Preview Chunking**:
   - If photo exists and `len(full_text) <= 1024`: send photo with caption and inline keyboard.
   - If photo exists and `len(full_text) > 1024`: send photo first; send text chunks sequentially. The approval keyboard (`reply_markup=kb`) is attached strictly to the **last chunk**, guaranteeing the buttons are visible and functional.
   - If no photo: send text chunks sequentially, attaching `reply_markup=kb` to the last chunk.
3. **Channel Publisher Chunking**:
   - If `post_text` exceeds 1024 chars with photo or exceeds 4000 chars without photo, it is safely split into sequential messages without throwing Telegram length errors.
4. **Prompt Optimization**:
   - Instruct the LLM in `build_system_prompt` to generate concise, mobile-friendly Telegram posts (600–1500 chars body, max 1800 chars), eliminating verbosity while retaining 100% of facts.

## Consequences
- Guaranteed delivery: Bot will never fail or drop buttons due to long text.
- Clean user experience: Posts stay concise, but even outlier articles are gracefully displayed with full interactive controls.
