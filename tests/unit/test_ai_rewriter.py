import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.domain.models import Tone, PostContent
from src.infrastructure.ai.prompts import build_system_prompt, build_user_prompt
from src.infrastructure.ai.llm_rewriter import OpenAIRewriter, RewriterError
from src.infrastructure.ai.composite import CompositeRewriter
from src.infrastructure.ai.image_generator import MockImageGenerator, DalleImageGenerator


def test_build_system_prompt_includes_tone():
    prompt_casual = build_system_prompt(Tone.CASUAL)
    assert "разговорный" in prompt_casual or "живой" in prompt_casual

    prompt_formal = build_system_prompt(Tone.FORMAL)
    assert "деловой" in prompt_formal or "экспертный" in prompt_formal


@pytest.mark.asyncio
async def test_openai_rewriter_success():
    client_mock = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "title": "Новый ИИ чип",
        "body": "Компания представила процессор нового поколения с удвоенной энергоэффективностью.",
        "hashtags": ["#AI", "#Hardware"],
        "image_prompt": "futuristic quantum microchip glowing with blue neon lights",
        "image_prompts": ["🎨 3D-рендер: микрочип в изометрии", "📸 Фото: лаборатория"],
    })
    client_mock.chat.completions.create = AsyncMock(return_value=MagicMock(choices=[mock_choice]))

    rewriter = OpenAIRewriter(api_key="test-key", model="gpt-4o-mini", client=client_mock)
    draft, img_prompt = await rewriter.rewrite_with_prompt("Исходная новость про чип...", Tone.DYNAMIC)

    assert draft.title == "Новый ИИ чип"
    assert "удвоенной энергоэффективностью" in draft.body
    assert draft.hashtags == ["#AI", "#Hardware"]
    assert img_prompt == "futuristic quantum microchip glowing with blue neon lights"
    assert len(draft.image_prompts) == 2


@pytest.mark.asyncio
async def test_dalle_image_generator_b64_json(tmp_path):
    import base64
    client_mock = MagicMock()
    # 1x1 transparent PNG in base64
    tiny_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    mock_item = MagicMock(url=None, b64_json=tiny_b64)
    client_mock.images.generate = AsyncMock(return_value=MagicMock(data=[mock_item]))

    img_dir = str(tmp_path / "images")
    gen = DalleImageGenerator(api_key="key", model="gpt-image-2", client=client_mock, images_dir=img_dir)
    asset = await gen.generate("Test prompt")

    assert asset.is_placeholder is False
    assert asset.image_url is not None
    assert asset.image_url.endswith(".png")


@pytest.mark.asyncio
async def test_composite_rewriter_fallback():
    primary_mock = MagicMock()
    primary_mock.rewrite_with_prompt = AsyncMock(side_effect=Exception("DeepSeek 503 Service Unavailable"))

    fallback_mock = MagicMock()
    fallback_draft = PostContent(title="Fallback Title", body="Fallback Body", hashtags=["#fallback"])
    fallback_mock.rewrite_with_prompt = AsyncMock(return_value=(fallback_draft, "fallback image prompt"))

    composite = CompositeRewriter(primary=primary_mock, fallback=fallback_mock)
    draft, img_prompt = await composite.rewrite_with_prompt("Test content", Tone.FORMAL)

    assert draft.title == "Fallback Title"
    assert img_prompt == "fallback image prompt"
    assert primary_mock.rewrite_with_prompt.called
    assert fallback_mock.rewrite_with_prompt.called


@pytest.mark.asyncio
async def test_mock_image_generator():
    gen = MockImageGenerator(default_image_url="https://placeholder.com/mock.png")
    asset = await gen.generate("any prompt")
    assert asset.image_url == "https://placeholder.com/mock.png"
    assert asset.is_placeholder is True
