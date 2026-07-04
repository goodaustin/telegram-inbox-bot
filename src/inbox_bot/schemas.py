from typing import Any, Literal
from pydantic import BaseModel, Field

Category = Literal[
    "restaurant", "place", "todo", "article",
    "quote", "apparel", "skincare", "photo", "inbox",
]


class ClassifierResult(BaseModel):
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    raw_text: str
    fields: dict[str, Any] = Field(default_factory=dict)


CATEGORY_FIELD_SCHEMAS: dict[Category, list[str]] = {
    "restaurant": ["name", "city", "cuisine", "notes"],
    "place":      ["name", "city", "type", "notes"],
    "todo":       ["task", "notes"],
    "article":    ["title", "url", "publisher", "summary"],
    "quote":      ["quote", "author", "tags"],
    "apparel":    ["item", "brand", "type", "price", "url", "notes"],
    "skincare":   ["product", "brand", "category", "price", "url", "notes"],
    "photo":      ["description", "notes"],
    "inbox":      ["reason"],
}
