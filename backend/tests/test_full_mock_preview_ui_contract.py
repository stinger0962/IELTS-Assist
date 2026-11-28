"""Keep isolated React examples aligned with the actual question-only DTO."""
import json
from pathlib import Path

import pytest

from app.services.full_mock_preview import active_mock_preview
from app.services.full_mock_renderer_bridge import RENDERER_VERSION
from tests.test_full_mock_audit import fixture


@pytest.mark.parametrize("skill", ["reading", "listening"])
def test_react_preview_fixture_matches_server_whitelist(skill):
    path = Path(__file__).resolve().parents[2] / "frontend/src/__tests__/fixtures/fullMockPreview.json"
    saved = json.loads(path.read_text())[skill]
    assert saved == active_mock_preview(fixture(skill), skill=skill, renderer_version=RENDERER_VERSION)
