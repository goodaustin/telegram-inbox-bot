from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

Category = Literal[
    "restaurant", "place", "todo", "article",
    "quote", "apparel", "skincare", "photo", "funny", "inbox",
]


class ClassifierResult(BaseModel):
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    raw_text: str
    fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        from inbox_bot.categories import all_category_keys
        if v not in all_category_keys():
            raise ValueError(f"unknown category: {v!r}")
        return v


CATEGORY_FIELD_SCHEMAS: dict[Category, list[str]] = {
    "restaurant": ["name", "city", "cuisine", "notes"],
    "place":      ["name", "city", "type", "notes"],
    "todo":       ["task", "notes"],
    "article":    ["title", "url", "publisher", "summary", "type"],
    "quote":      ["quote", "author", "tags"],
    "apparel":    ["item", "brand", "type", "price", "url", "notes"],
    "skincare":   ["product", "brand", "category", "price", "url", "notes"],
    "photo":      ["description", "notes"],
    "funny":      ["caption", "tags", "notes"],
    "inbox":      ["reason"],
}
