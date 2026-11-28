"""Shared JSON snapshots connect actual DOM tests to the pure pinned bridge."""
import json
from pathlib import Path

import pytest

from app.services.full_mock_renderer_bridge import RENDERER_VERSION, renderer_key_map


@pytest.mark.parametrize("name,skill", [
    ("reading", "reading"), ("listening", "listening"), ("listeningEmpty", "listening"),
])
def test_dom_fixture_expected_keys_match_bridge(name, skill):
    path = Path(__file__).resolve().parents[2] / "frontend/src/__tests__/fixtures/fullMockRenderer.json"
    fixture = json.loads(path.read_text())[name]
    actual = renderer_key_map(fixture["exercise"], skill=skill, renderer_version=RENDERER_VERSION)
    assert {str(section): keys for section, keys in actual.items()} == fixture["keys"]
    assert sum(map(len, actual.values())) == 40
