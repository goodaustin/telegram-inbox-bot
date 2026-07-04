import pytest
from pydantic import ValidationError
from inbox_bot.schemas import ClassifierResult, CATEGORY_FIELD_SCHEMAS


def test_classifier_result_accepts_restaurant():
    r = ClassifierResult(
        category="restaurant",
        confidence=0.95,
        raw_text="Tonkatsu Maisen 東京 表參道",
        fields={"name": "Maisen", "city": "東京/表參道", "cuisine": ["日料", "炸物"]},
    )
    assert r.category == "restaurant"
    assert r.fields["name"] == "Maisen"


def test_classifier_result_rejects_invalid_category():
    with pytest.raises(ValidationError):
        ClassifierResult(category="movies", confidence=0.9, raw_text="x", fields={})


def test_classifier_result_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        ClassifierResult(category="todo", confidence=1.5, raw_text="x", fields={})


def test_all_categories_have_field_schema():
    expected = {"restaurant", "place", "todo", "article", "quote",
                "apparel", "skincare", "photo", "inbox"}
    assert set(CATEGORY_FIELD_SCHEMAS.keys()) == expected


def test_photo_schema_has_expected_fields():
    assert CATEGORY_FIELD_SCHEMAS["photo"] == ["description", "notes"]


def test_inbox_schema_is_minimal():
    assert CATEGORY_FIELD_SCHEMAS["inbox"] == ["reason"]


def test_restaurant_schema_has_expected_fields():
    assert "name" in CATEGORY_FIELD_SCHEMAS["restaurant"]
    assert "city" in CATEGORY_FIELD_SCHEMAS["restaurant"]


def test_article_schema_includes_type():
    assert CATEGORY_FIELD_SCHEMAS["article"] == [
        "title", "url", "publisher", "summary", "type"
    ]
