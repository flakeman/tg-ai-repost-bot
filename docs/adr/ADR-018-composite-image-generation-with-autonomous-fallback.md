# ADR-018: Composite Image Generation with Autonomous Fallback Provider

## Status
Accepted

## Context
1. **Provider Heterogeneity**: When users switch between LLM gateways (such as from `cheapvibecode.ru` to `api.ewoi.tech`), some providers offer only text completions and do not support image generation endpoints (`POST /v1/images/generations` returns HTTP 403 `model_not_allowed`).
2. **Missing Cover Art**: When the active gateway lacks image models, `DalleImageGenerator` caught the 403 error and returned an `is_placeholder=True` asset. Consequently, posts were generated without cover images ("картинки не генерит"), forcing text-only delivery unless an image was present in the forwarded post.
3. **Requirement for High-Availability Visuals**: Telegram channels require consistent visual cover art to maximize user engagement. The pipeline must not degrade to text-only mode merely because a specific commercial gateway lacks multimodal/image endpoints.

## Decision
1. **Implement `PollinationsImageGenerator`**:
   - Introduce an autonomous, keyless image generator adapter implementing `IImageGenerator`.
   - Utilizes Pollinations AI (`https://image.pollinations.ai/prompt/...`) with Flux / SD pipelines to render high-definition 1024x1024 editorial illustrations.
   - Downloads generated binary bytes via asynchronous HTTP client (`httpx.AsyncClient`) and saves them locally into `storage/images/gen_{uuid}.jpg`.
2. **Implement `CompositeImageGenerator`**:
   - Adopts the Composite / Chain of Responsibility pattern for image generation.
   - Attempts generation via `primary` (e.g. `DalleImageGenerator`).
   - If the primary provider fails (HTTP 403 `model_not_allowed`, quota exhaustion, network timeout) or returns a placeholder, the composite automatically executes `fallback.generate(prompt)` (`PollinationsImageGenerator`).
   - If both providers fail or connectivity is offline, returns a placeholder asset with prompt suggestions.
3. **Integration in Main Composition Root (`src/main.py`)**:
   - Wire `CompositeImageGenerator(primary=dalle_gen, fallback=pollinations_gen)` as the standard image generator for the publishing pipeline.

## Consequences
- 100% cover image generation reliability regardless of whether the active LLM gateway supports image endpoints.
- Smooth transition: zero configuration overhead when users switch LLM keys.
- Preserves full backward compatibility with user-defined style prompts and local storage TTL cleanup.
