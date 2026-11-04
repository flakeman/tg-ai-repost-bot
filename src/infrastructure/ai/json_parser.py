import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RobustJsonParser:
    @classmethod
    def parse(cls, raw_content: str) -> Dict[str, Any]:
        """
        Parses JSON output from LLM with multi-stage sanitization
        and regex fallback for malformed JSON strings.
        """
        text = raw_content.strip()

        # 1. Strip markdown fences
        if "```" in text:
            # Extract content within ```json ... ``` or ``` ... ```
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                text = match.group(1).strip()
            else:
                text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
                text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)

        # 2. Try standard json.loads
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 3. Clean common LLM JSON syntax quirks:
        # Remove trailing commas: e.g. [1, 2, ] or {"a": 1, }
        cleaned = re.sub(r",\s*([\]}])", r"\1", text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 4. Regex fallback extraction of standard keys
        logger.warning("Standard JSON parsing failed, attempting regex fallback on content: %s", raw_content[:150])
        result = {}

        # title
        m_title = re.search(r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', text)
        if m_title:
            result["title"] = m_title.group(1).replace(r"\"", '"').replace(r"\n", " ").strip()

        # body
        m_body = re.search(r'"body"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', text)
        if m_body:
            result["body"] = m_body.group(1).replace(r'\"', '"').replace(r"\n", "\n").strip()
        else:
            # Fallback for truncated/unclosed body string
            m_body_trunc = re.search(r'"body"\s*:\s*"(.*?)(?:",|\s*"\s*\}|\s*\}\s*$|$)', text, flags=re.DOTALL)
            if m_body_trunc:
                result["body"] = m_body_trunc.group(1).replace(r'\"', '"').replace(r"\n", "\n").strip()

        # hashtags
        m_tags = re.search(r'"hashtags"\s*:\s*\[(.*?)\]', text, flags=re.DOTALL)
        if m_tags:
            tags_str = m_tags.group(1)
            result["hashtags"] = [
                t.strip().strip('"').strip("'")
                for t in tags_str.split(",")
                if t.strip() and t.strip().strip('"').strip("'").startswith("#")
            ]

        # image_prompt
        m_img = re.search(r'"image_prompt"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', text)
        if m_img:
            result["image_prompt"] = m_img.group(1).replace(r"\"", '"').strip()

        # image_prompts list
        m_imgs = re.search(r'"image_prompts"\s*:\s*\[(.*?)\]', text, flags=re.DOTALL)
        if m_imgs:
            prompts_raw = m_imgs.group(1)
            result["image_prompts"] = [
                p.strip().strip('"').strip("'")
                for p in prompts_raw.split('",')
                if p.strip()
            ]

        if "body" in result and result["body"]:
            return result

        raise ValueError(f"Failed to parse LLM JSON payload: {raw_content[:200]}")
