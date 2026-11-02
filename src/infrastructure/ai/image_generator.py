import base64
import logging
import os
import uuid
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
        images_dir: str = "storage/images",
    ):
        self.model = model
        self.style_modifier = style_modifier
        self.client = client or AsyncOpenAI(api_key=api_key)
        self.images_dir = images_dir
        os.makedirs(self.images_dir, exist_ok=True)

    async def generate(self, prompt: str) -> ImageAsset:
        full_prompt = f"{prompt.strip()}. Style: {self.style_modifier}"
        try:
            kwargs = {
                "model": self.model,
                "prompt": full_prompt[:950],
                "n": 1,
            }
            if "dall-e" in self.model:
                kwargs["size"] = "1024x1024"
                kwargs["quality"] = "standard"

            response = await self.client.images.generate(**kwargs)
            item = response.data[0]

            image_url = getattr(item, "url", None)
            b64_json = getattr(item, "b64_json", None)

            if b64_json:
                img_bytes = base64.b64decode(b64_json)
                filename = f"gen_{uuid.uuid4().hex[:12]}.png"
                filepath = os.path.join(self.images_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(img_bytes)
                image_url = filepath

            if image_url:
                return ImageAsset(image_url=image_url, prompt_used=full_prompt, is_placeholder=False)
            return ImageAsset(image_url=None, prompt_used=full_prompt, is_placeholder=True)
        except Exception as exc:
            logger.error("Image generation failed: %s", exc)
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
