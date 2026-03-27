"""Basic tests for niche finder (no API calls)."""

import pytest
from modules.niche_finder import _parse_niches, Niche


def test_parse_valid_niches():
    raw = '''[
      {
        "name": "Motivational Quotes",
        "score": 9.0,
        "keywords": ["motivation", "success", "mindset"],
        "content_angles": ["Morning routines", "Success stories"],
        "rationale": "Always trending"
      },
      {
        "name": "Finance Tips",
        "score": 8.5,
        "keywords": ["money", "investing", "budget"],
        "content_angles": ["Saving hacks", "Investing basics"],
        "rationale": "High CPM"
      }
    ]'''
    niches = _parse_niches(raw)
    assert len(niches) == 2
    assert niches[0].name == "Motivational Quotes"
    assert niches[0].score == 9.0
    assert "motivation" in niches[0].keywords
    assert len(niches[0].content_angles) == 2


def test_parse_invalid_json_returns_empty():
    niches = _parse_niches("not json")
    assert niches == []


def test_niche_str_representation():
    n = Niche(name="Test Niche", score=7.5, keywords=["kw1", "kw2"])
    s = str(n)
    assert "7.5/10" in s
    assert "Test Niche" in s
