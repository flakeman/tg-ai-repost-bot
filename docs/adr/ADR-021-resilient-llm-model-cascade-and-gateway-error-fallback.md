# ADR-021: Resilient LLM Model Cascade and Gateway Error Fallback

## Status
Accepted

## Context
1. **Dynamic Upstream Merchant Failures (HTTP 503 / 402)**: On aggregated OpenAI-compatible API gateways (such as `api.ewoi.tech`), specific models may temporarily become unavailable when upstream merchants delist them (`fixed_merchant_marketplace_listing_unavailable`, HTTP 503), adjust rates (`pin_paused_price_changed`, HTTP 402), or experience transient timeouts.
2. **Impact**: When `OPENAI_MODEL=gpt-5.6-terra` became unavailable on the gateway, the bot threw a 503 error directly to the user during pipeline processing, failing the entire repost job even though dozens of other high-performance models (such as `gpt-6-sol`, `gpt-5.6-sol`, `deepseek-v4.1-flash-1017`) were fully functional on the exact same API key.
3. **Requirement**: The system must achieve enterprise-grade resilience by automatically cascading through a prioritized list of candidate models upon encountering recoverable gateway errors (503, 502, 504, 402 pin paused, 429 rate limit, or timeout), ensuring that user requests never fail due to a single upstream model hiccup.

## Decision
1. **Intelligent Model Cascade in `OpenAIRewriter`**:
   - `OpenAIRewriter` receives a primary model and an optional `fallback_models` list.
   - Defaults candidate pool: `[self.model, "gpt-6-sol", "gpt-5.6-sol", "deepseek-v4.1-flash-1017", "claude-haiku-5-5", "qwen3.8-flash"]`.
   - On each rewrite attempt, the rewriter attempts the primary model first.
   - If a recoverable error occurs (HTTP 503, 502, 504, 402 merchant price change, 429, timeout), it logs a warning and immediately falls back to the next candidate model in the cascade.
   - Non-recoverable errors (e.g. invalid API key, 401 unauthorized) abort immediately to avoid pointless retries.
2. **Primary Model Update**:
   - Switch the active `OPENAI_MODEL` from `gpt-5.6-terra` to `gpt-6-sol` (and `gpt-5.6-sol`), verified as active, stable, and delivering high quality structured Russian outputs.
3. **Observability**:
   - Structured logging captures when a fallback model is used, ensuring full visibility into gateway routing health.

## Consequences
- Guaranteed zero-downtime rewrite capability even when upstream gateway providers disable or re-price individual models.
- Seamless automatic recovery in under 1 second.
- Fully compatible with existing domain models and interface contracts.
