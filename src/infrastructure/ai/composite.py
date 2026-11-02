import logging
from typing import Optional, Tuple
from src.domain.interfaces import ILLMRewriter
from src.domain.models import Tone, PostContent

logger = logging.getLogger(__name__)


class CompositeRewriter(ILLMRewriter):
    def __init__(self, primary: ILLMRewriter, fallback: Optional[ILLMRewriter] = None):
        self.primary = primary
        self.fallback = fallback

    async def rewrite_with_prompt(
        self, raw_text: str, tone: Tone, title_hint: Optional[str] = None
    ) -> Tuple[PostContent, Optional[str]]:
        try:
            if hasattr(self.primary, "rewrite_with_prompt"):
                return await self.primary.rewrite_with_prompt(raw_text, tone, title_hint)
            draft = await self.primary.rewrite(raw_text, tone, title_hint)
            return draft, None
        except Exception as primary_err:
            logger.warning("Primary LLM provider failed: %s. Attempting fallback...", primary_err)
            if not self.fallback:
                raise primary_err

            if hasattr(self.fallback, "rewrite_with_prompt"):
                return await self.fallback.rewrite_with_prompt(raw_text, tone, title_hint)
            draft = await self.fallback.rewrite(raw_text, tone, title_hint)
            return draft, None

    async def rewrite(self, raw_text: str, tone: Tone, title_hint: Optional[str] = None) -> PostContent:
        draft, _ = await self.rewrite_with_prompt(raw_text, tone, title_hint)
        return draft
