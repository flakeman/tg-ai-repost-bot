import asyncio
import base64
import logging
import os
import re
import uuid
from typing import Optional
import httpx
from openai import AsyncOpenAI
from src.domain.interfaces import IImageGenerator
from src.domain.models import ImageAsset

logger = logging.getLogger(__name__)

SENSITIVE_REPLACEMENTS = [
    (r"\b(donald\s+)?trump\b", "diplomat"),
    (r"\b(vladimir\s+)?putin\b", "statesman"),
    (r"\b(joe\s+)?biden\b", "president"),
    (r"\b(kamala\s+)?harris\b", "official"),
    (r"\b(volodymyr\s+)?zelensky\b", "leader"),
    (r"\b(war|warfare|battlefield|bloodshed|missiles?|weapons?|bombing|invasion)\b", "geopolitical summit"),
]


def sanitize_image_prompt(prompt: str) -> str:
    cleaned = prompt
    for pattern, replacement in SENSITIVE_REPLACEMENTS:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    return cleaned


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

    async def generate(self, prompt: str, max_retries: int = 4) -> ImageAsset:
        raw_prompt = prompt.strip()
        sanitized = sanitize_image_prompt(raw_prompt)

        if "Style:" not in sanitized and self.style_modifier:
            full_prompt = f"{sanitized}. Style: {self.style_modifier}"
        else:
            full_prompt = sanitized

        prompts_to_try = [
            full_prompt[:950],
            # Fallback 1: shorter core summary
            sanitized.split(".")[0][:400] + (f". Style: {self.style_modifier}" if self.style_modifier else ""),
            # Fallback 2: minimal concise prompt
            sanitized[:250],
            # Fallback 3: generic conceptual prompt
            f"Minimalist modern news editorial illustration, diplomatic and technological concept. Style: {self.style_modifier}",
        ]

        # Model rotation if primary fails (supports cheapvibecode and OpenAI)
        candidate_models = [self.model]
        for fallback_m in ["gpt-image-2.5-flare", "gpt-image-1", "gpt-image-2"]:
            if fallback_m not in candidate_models:
                candidate_models.append(fallback_m)

        last_error = None
        for attempt in range(max_retries):
            current_prompt = prompts_to_try[attempt % len(prompts_to_try)]
            current_model = candidate_models[attempt % len(candidate_models)]

            try:
                kwargs = {
                    "model": current_model,
                    "prompt": current_prompt,
                    "n": 1,
                }
                if "dall-e" in current_model:
                    kwargs["size"] = "1024x1024"
                    kwargs["quality"] = "standard"

                logger.info("Generating image (attempt %d/%d) with model %s...", attempt + 1, max_retries, current_model)
                response = await self.client.images.generate(**kwargs)

                if not response or not getattr(response, "data", None) or len(response.data) == 0:
                    err_msg = getattr(response, "error", None) or "Empty response data"
                    raise RuntimeError(f"Image API returned no data: {err_msg}")

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
                elif image_url and image_url.startswith("http"):
                    try:
                        async with httpx.AsyncClient(timeout=30.0) as hclient:
                            r = await hclient.get(image_url)
                            if r.status_code == 200:
                                filename = f"gen_{uuid.uuid4().hex[:12]}.png"
                                filepath = os.path.join(self.images_dir, filename)
                                with open(filepath, "wb") as f:
                                    f.write(r.content)
                                image_url = filepath
                    except Exception as down_err:
                        logger.warning("Failed to download image from URL %s: %s", image_url, down_err)

                if image_url:
                    logger.info("Image generated successfully on attempt %d with model %s: %s", attempt + 1, current_model, image_url)
                    return ImageAsset(image_url=image_url, prompt_used=current_prompt, is_placeholder=False)

            except Exception as exc:
                last_error = exc
                logger.warning("Image generation attempt %d failed (model %s): %s.", attempt + 1, current_model, exc)
                err_str = str(exc).lower()
                if "model_not_allowed" in err_str or "403" in err_str or "not supported" in err_str or "unsupported" in err_str:
                    logger.warning("Image generation not supported by provider, aborting retries.")
                    break
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 * (attempt + 1))

        logger.error("All image generation attempts failed. Last error: %s", last_error)
        return ImageAsset(image_url=None, prompt_used=full_prompt, is_placeholder=True)


def remove_pollinations_watermark(image_bytes: bytes) -> bytes:
    """
    Pollinations AI stamps a branding logo/watermark in the bottom-right corner
    (within bottom ~6.5% of height). This function crops that bottom slice
    and resizes the image back to its original dimensions cleanly.
    """
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(image_bytes))
        w, h = im.size
        # The watermark is in the bottom right corner, within the bottom ~6.5% of image height
        bottom_cut = max(48, int(h * 0.065))
        cropped = im.crop((0, 0, w, h - bottom_cut))
        res = cropped.resize((w, h), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        save_format = im.format or "JPEG"
        if save_format.upper() in ("JPG", "JPEG"):
            res.save(out, format="JPEG", quality=95)
        else:
            res.save(out, format=save_format)
        return out.getvalue()
    except Exception as exc:
        logger.warning("Could not auto-crop watermark from image: %s", exc)
        return image_bytes


class PollinationsImageGenerator(IImageGenerator):
    """
    Autonomous fallback image generator using Pollinations.ai (Flux/SD).
    Requires no API key and provides reliable editorial cover art generation.
    """
    def __init__(
        self,
        style_modifier: str = "modern minimalist, high quality digital editorial illustration",
        images_dir: str = "storage/images",
        timeout: float = 45.0,
    ):
        self.style_modifier = style_modifier
        self.images_dir = images_dir
        self.timeout = timeout
        os.makedirs(self.images_dir, exist_ok=True)

    async def generate(self, prompt: str) -> ImageAsset:
        import random
        import urllib.parse
        import re
        import asyncio

        raw_prompt = prompt.strip()
        sanitized = sanitize_image_prompt(raw_prompt)
        if "Style:" not in sanitized and self.style_modifier:
            full_prompt = f"{sanitized}. Style: {self.style_modifier}"
        else:
            full_prompt = sanitized

        encoded_prompt = urllib.parse.quote(full_prompt[:500])
        candidate_models = ["flux", "turbo", ""]
        max_attempts = 3

        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            for attempt in range(max_attempts):
                seed = random.randint(1, 2147483647)
                model_param = candidate_models[attempt % len(candidate_models)]
                url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&seed={seed}"
                if model_param:
                    url += f"&model={model_param}"

                logger.info(
                    "Generating image via Pollinations AI (attempt %d/%d, model: %s, seed: %d)...",
                    attempt + 1,
                    max_attempts,
                    model_param or "default",
                    seed,
                )
                try:
                    resp = await client.get(url, follow_redirects=True)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        cleaned_bytes = remove_pollinations_watermark(resp.content)
                        filename = f"gen_pol_{uuid.uuid4().hex[:12]}.jpg"
                        filepath = os.path.join(self.images_dir, filename)
                        with open(filepath, "wb") as f:
                            f.write(cleaned_bytes)
                        logger.info("Pollinations image successfully generated and saved (watermark stripped): %s", filepath)
                        return ImageAsset(image_url=filepath, prompt_used=full_prompt, is_placeholder=False)

                    # Handle 402 / 503 rate limits and temporary service overloads
                    if resp.status_code in (402, 503):
                        wait_match = re.search(r"Retry after (\d+)s", resp.text)
                        wait_s = int(wait_match.group(1)) if wait_match else (2 * (attempt + 1))
                        wait_s = min(wait_s, 15)
                        logger.warning(
                            "Pollinations rate limited (status %d). Waiting %d seconds before retry...",
                            resp.status_code,
                            wait_s,
                        )
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(wait_s + 0.5)
                            continue
                    else:
                        logger.warning("Pollinations returned status %d (length %d)", resp.status_code, len(resp.content))

                except Exception as exc:
                    logger.warning("Pollinations attempt %d failed: %s", attempt + 1, exc)
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(2)

        return ImageAsset(image_url=None, prompt_used=full_prompt, is_placeholder=True)


class CompositeImageGenerator(IImageGenerator):
    """
    Composite image generator implementing Tier 1 (primary, e.g. DALL-E)
    with automatic Tier 2 fallback (e.g. Pollinations AI).
    """
    def __init__(self, primary: IImageGenerator, fallback: Optional[IImageGenerator] = None):
        self.primary = primary
        self.fallback = fallback

    async def generate(self, prompt: str) -> ImageAsset:
        try:
            asset = await self.primary.generate(prompt)
            if asset and asset.image_url and not asset.is_placeholder:
                return asset
            logger.info("Primary image generator returned placeholder. Attempting fallback...")
        except Exception as exc:
            logger.warning("Primary image generator failed: %s. Attempting fallback...", exc)

        if self.fallback:
            try:
                fallback_asset = await self.fallback.generate(prompt)
                if fallback_asset and fallback_asset.image_url and not fallback_asset.is_placeholder:
                    logger.info("Fallback image generator succeeded: %s", fallback_asset.image_url)
                    return fallback_asset
            except Exception as fb_exc:
                logger.error("Fallback image generator failed: %s", fb_exc)

        return ImageAsset(image_url=None, prompt_used=prompt, is_placeholder=True)


class MockImageGenerator(IImageGenerator):
    def __init__(self, default_image_url: Optional[str] = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1000&q=80"):
        self.default_image_url = default_image_url

    async def generate(self, prompt: str) -> ImageAsset:
        return ImageAsset(
            image_url=self.default_image_url,
            prompt_used=prompt,
            is_placeholder=True,
        )
