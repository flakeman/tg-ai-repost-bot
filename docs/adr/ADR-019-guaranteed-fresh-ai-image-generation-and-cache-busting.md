# ADR-019: Guaranteed Fresh AI Image Generation and Random Seed Cache-Busting

## Status
Accepted

## Context
1. **Unintended Retention of Forwarded Donor Images**: In ADR-017, incoming forwarded photos were saved into `job.image`, and `orchestrator.process_pipeline` checked `if job.image: retain original image`. As a result, any forwarded post completely bypassed AI image generation, presenting the user with the donor channel's existing picture instead of a new AI-generated editorial cover.
2. **Corrupted Prompt on Regeneration**: When `job.image` was set from a forwarded photo with `prompt_used="forwarded telegram media"`, subsequent calls to `regenerate_image` passed that literal string as the image prompt instead of using the news article's actual visual concept prompt.
3. **CDN Caching in Fallback Image Generator**: `PollinationsImageGenerator` requested `https://image.pollinations.ai/prompt/{encoded_prompt}` without a random seed parameter. Pollinations' CDN aggressively caches responses by prompt URL, returning the exact same image byte-for-byte upon repeated generation requests for the same or similar prompts.

## Decision
1. **Always Synthesize Fresh AI Cover Art**:
   - In `process_pipeline`, image generation is ALWAYS executed for every post.
   - The primary prompt used is `img_prompt` (derived from LLM rewrite), with fallback to the first suggested concept in `draft.image_prompts`, or `Editorial illustration for news: {draft.title}`.
   - Forwarded images from Telegram are preserved as optional fallback only if all AI generation attempts fail, rather than pre-empting generative synthesis.
2. **Dynamic Random Seed in PollinationsImageGenerator**:
   - Append `&seed={random.randint(1, 2147483647)}` and `&model=flux` to every Pollinations AI request.
   - This bypasses CDN cache locks and guarantees that every single generation or re-generation produces a unique, high-fidelity visual artwork.
3. **Intelligent Regeneration Prompt Cycling in `regenerate_image`**:
   - In `regenerate_image`, prioritize `job.draft.image_prompts` if available, cycling through alternative concepts or using `f"{job.draft.title}. Concept: {concept}"` with a fresh seed.
   - Never pass generic fallback strings like `"forwarded telegram media"` into the image generator.

## Consequences
- Every post receives a brand-new, unique AI illustration.
- Clicking «🎨 Перегенерировать обложку» produces visibly distinct visual variants on every click.
- Eliminates stale CDN image reuse across similar topics.
