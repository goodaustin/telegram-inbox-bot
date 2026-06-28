import asyncio
import base64
from importlib import resources
from typing import Any
from anthropic import AsyncAnthropic
from inbox_bot.config import Settings
from inbox_bot.schemas import ClassifierResult


class ClassifierError(Exception):
    pass


CLASSIFY_TOOL: dict[str, Any] = {
    "name": "classify_item",
    "description": "Classify an inbox item and extract structured fields.",
    "input_schema": {
        "type": "object",
        "required": ["category", "confidence", "raw_text", "fields"],
        "properties": {
            "category": {
                "type": "string",
                "enum": ["restaurant", "place", "todo", "article",
                         "quote", "apparel", "skincare", "inbox"],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "raw_text": {"type": "string"},
            "fields": {"type": "object"},
        },
    },
}


def _load_system_prompt() -> str:
    return resources.files("inbox_bot.prompts").joinpath("classify.md").read_text(encoding="utf-8")


def _build_content(image_bytes: bytes | None, text: str | None) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    if image_bytes:
        parts.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(image_bytes).decode("ascii"),
            },
        })
    if text:
        parts.append({"type": "text", "text": text})
    if not parts:
        parts.append({"type": "text", "text": "(empty)"})
    return parts


async def classify(
    *,
    image_bytes: bytes | None,
    text: str | None,
    settings: Settings,
    client: AsyncAnthropic | None = None,
) -> ClassifierResult:
    if client is None:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    system = _load_system_prompt()
    content = _build_content(image_bytes, text)

    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            resp = await client.messages.create(
                model=settings.classifier_model,
                max_tokens=1024,
                system=system,
                tools=[CLASSIFY_TOOL],
                tool_choice={"type": "tool", "name": "classify_item"},
                messages=[{"role": "user", "content": content}],
            )
            tool_block = next(
                (b for b in resp.content if getattr(b, "type", None) == "tool_use"),
                None,
            )
            if tool_block is None:
                raise ClassifierError("no tool_use block in response")

            result = ClassifierResult(**tool_block.input)
            if result.confidence < settings.confidence_threshold:
                return ClassifierResult(
                    category="inbox",
                    confidence=result.confidence,
                    raw_text=result.raw_text,
                    fields={
                        "original_category": result.category,
                        "reason": "low_confidence",
                        **result.fields,
                    },
                )
            return result
        except Exception as e:
            last_err = e
            if attempt == 1:
                await asyncio.sleep(2)
                continue
            raise ClassifierError(f"classifier failed after retry: {e}") from e

    raise ClassifierError(f"unreachable: {last_err}")
