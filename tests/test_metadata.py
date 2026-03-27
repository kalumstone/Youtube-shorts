"""Basic tests for metadata generator (no API calls)."""

import pytest
from modules.metadata_generator import _parse_metadata, VideoMetadata


def test_parse_valid_json():
    raw = '''
    {
      "title": "5 Life Hacks That Will Change Your Life",
      "description": "These life hacks are incredible...",
      "tags": ["life hacks", "productivity", "tips"],
      "hashtags": ["#Shorts", "#LifeHacks"],
      "category_id": "26",
      "thumbnail_text": "Life Hacks"
    }
    '''
    meta = _parse_metadata(raw)
    assert meta.title == "5 Life Hacks That Will Change Your Life"
    assert "life hacks" in meta.tags
    assert meta.category_id == "26"
    assert "#Shorts" in meta.hashtags


def test_parse_markdown_wrapped_json():
    raw = '''```json
    {
      "title": "Test Title",
      "description": "Test desc",
      "tags": ["test"],
      "hashtags": ["#Shorts"],
      "category_id": "22",
      "thumbnail_text": "Test"
    }
    ```'''
    meta = _parse_metadata(raw)
    assert meta.title == "Test Title"


def test_parse_invalid_json_returns_default():
    meta = _parse_metadata("This is not JSON at all")
    assert isinstance(meta, VideoMetadata)
    assert meta.title  # Should have some default title


def test_tags_string_truncates_at_500():
    meta = VideoMetadata(
        title="Test",
        description="Test",
        tags=["a" * 30] * 30,  # 30 tags of 30 chars each
    )
    assert len(meta.tags_string()) <= 500


def test_full_description_includes_hashtags():
    meta = VideoMetadata(
        title="Test",
        description="My description",
        hashtags=["#Shorts", "#YouTube"],
    )
    full = meta.full_description()
    assert "#Shorts" in full
    assert "My description" in full
