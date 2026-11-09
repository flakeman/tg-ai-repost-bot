# ADR-020: Extraction of Article Keys/Entities and Mandatory Keyword Integration in AI Image Generation

## Status
Accepted

## Context
1. **Generic Image Prompts**: Previously, image generation prompts could drift toward overly abstract metaphors or generic aesthetics (e.g., "modern digital cyberspace with glowing lines") rather than visually depicting the specific technologies, physical hardware, cryptographic keys, identifiers, entities, and core subject matter of the news article.
2. **User Requirement**: *"пусть в генерации картинки используются ключи из статьи"* (Let the image generation use keys / keywords from the article).
3. **Multi-Concept Alignment**: When cycling through alternative visual styles during image regeneration, each variant should still be anchored around the article's actual key entities, technologies, and terms.
4. **Keyword Persistence**: Extracted keywords must be part of the aggregate model and stored in the database so subsequent interactions and regenerations retain the contextual keys of the original article.

## Decision
1. **Domain Model Enhancement (`PostContent.keywords`)**:
   - Add `keywords: List[str]` to the `PostContent` domain model.
   - Store normalized keywords in SQLite via `keywords_json TEXT` column in `publishing_jobs`.
2. **LLM Prompt Engineering for Key Extraction and Visual Anchoring**:
   - Update `build_system_prompt` in `src/infrastructure/ai/prompts.py`:
     - Require LLM to extract 3–7 core entities, technologies, physical objects, and domain keys into `"keywords"`.
     - In `"image_prompt"`, mandate that the English image prompt explicitly integrates these core keywords, physical devices, schemas, identifiers, and domain keys to produce highly relevant, context-rich editorial art.
     - In `"image_prompts"` (alternative style concepts), mandate that each visual concept incorporates the key objects and terms from the article.
3. **Orchestrator Keyword Reinforcement**:
   - In `process_pipeline` and `regenerate_image`, when constructing the prompt for `IImageGenerator`, ensure the article's key terms are explicitly woven into the generation prompt (`featuring key elements: ...`) if not already present.
   - For alternative prompts during regeneration, append the English key terms so English-first diffusion models (Flux/SD/DALL-E) accurately render the specific subjects.
4. **Robust Parsing and Schema Migration**:
   - Update `_parse_json_payload` in `llm_rewriter.py` and `json_parser.py` to extract `keywords`.
   - Update `database.py` with automatic column migration for `keywords_json` and `repositories.py` to serialize/deserialize it.

## Consequences
- Every generated cover image visibly reflects the real subject matter, hardware, technologies, and keys of the news article.
- Alternative styles during regeneration remain faithful to the article's core subject matter.
- Full compliance with DDD/SDD architectural rules and 100% automated test coverage.
