import asyncio
import base64
import json
from importlib import resources
from typing import Any
from openai import AsyncOpenAI
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

# OpenAI function-calling wrapper around CLASSIFY_TOOL's schema.
_OPENAI_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": CLASSIFY_TOOL["name"],
        "description": CLASSIFY_TOOL["description"],
        "parameters": CLASSIFY_TOOL["input_schema"],
    },
}


def _load_system_prompt() -> str:
    return resources.files("inbox_bot.prompts").joinpath("classify.md").read_text(encoding="utf-8")


def _build_content(image_bytes: bytes | None, text: str | None) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
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
    client: AsyncOpenAI | None = None,
) -> ClassifierResult:
    if client is None:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

    system = _load_system_prompt()
    content = _build_content(image_bytes, text)

    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            resp = await client.chat.completions.create(
                model=settings.classifier_model,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
                tools=[_OPENAI_TOOL],
                tool_choice={"type": "function", "function": {"name": "classify_item"}},
            )
            tool_calls = resp.choices[0].message.tool_calls
            if not tool_calls:
                raise ClassifierError("no tool_calls in response")

            args = json.loads(tool_calls[0].function.arguments)
            result = ClassifierResult(**args)
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
        except ClassifierError:
            # structural failure — don't retry, don't wrap
            raise
        except Exception as e:
            last_err = e
            if attempt == 1:
                await asyncio.sleep(2)
                continue
            raise ClassifierError(f"classifier failed after retry: {e}") from e

    raise ClassifierError(f"unreachable: {last_err}")
