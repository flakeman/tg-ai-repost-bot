import logging
from typing import Optional
from openai import AsyncOpenAI
from src.domain.interfaces import IImageGenerator
from src.domain.models import ImageAsset

logger = logging.getLogger(__name__)


class DalleImageGenerator(IImageGenerator):
    def __init__(
        self,
        api_key: str,
        model: str = "dall-e-3",
        style_modifier: str = "modern minimalist, high quality digital editorial illustration",
        client: Optional[AsyncOpenAI] = None,
    ):
        self.model = model
        self.style_modifier = style_modifier
        self.client = client or AsyncOpenAI(api_key=api_key)

    async def generate(self, prompt: str) -> ImageAsset:
        full_prompt = f"{prompt.strip()}. Style: {self.style_modifier}"
        try:
            response = await self.client.images.generate(
                model=self.model,
                prompt=full_prompt[:950],
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
            return ImageAsset(image_url=image_url, prompt_used=full_prompt, is_placeholder=False)
        except Exception as exc:
            logger.error("DALL-E image generation failed: %s", exc)
            # Return placeholder with graceful degradation
            return ImageAsset(image_url=None, prompt_used=full_prompt, is_placeholder=True)


class MockImageGenerator(IImageGenerator):
    def __init__(self, default_image_url: Optional[str] = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1000&q=80"):
        self.default_image_url = default_image_url

    async def generate(self, prompt: str) -> ImageAsset:
        return ImageAsset(
            image_url=self.default_image_url,
            prompt_used=prompt,
            is_placeholder=True,
        )
