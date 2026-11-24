"""Fixture launchers stop implicit provider work without disabling DB exercises."""
import json
import socket
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.main import app
from app.models.models import GeneratedPractice, UserPractice
from app.routers import grammar, listening, reading, writing
from tests.test_writing_study_pass import ESSAY, GRADE
from app.staging import _load_fixture_app


@pytest.fixture(params=[True, False], ids=["guarded", "default"])
def fixture_app(request, monkeypatch):
    if request.param:
        # Keep app.state from leaking across test cases.
        monkeypatch.setattr(app, "state", type(app.state)())
        assert _load_fixture_app() is app
    return request.param


@pytest.fixture(autouse=True)
def no_provider_network(monkeypatch):
    monkeypatch.setattr(settings, "DAILY_GENERATION_ENABLED", False)
    def deny_network(*args, **kwargs):
        pytest.fail("provider network use is prohibited in this regression")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)


@pytest.mark.parametrize("skill,module,generator,method,more", [
    ("grammar", grammar, grammar.grammar_generator, "generate", "generate-more-grammar"),
    ("listening", listening, listening.listening_generator, "generate", "generate-more-listening"),
    ("reading", reading, reading.practice_generator, "generate_practice", "generate-more"),
])
def test_provider_backed_learner_routes_skip_only_fixture_background_work(
    skill, module, generator, method, more, fixture_app, client, test_db, test_user,
    auth_token, monkeypatch,
):
    # The scheduler switch alone must not suppress request-driven top-ups.
    assert settings.DAILY_GENERATION_ENABLED is False
    monkeypatch.setattr(module, "SessionLocal", sessionmaker(bind=test_db.get_bind()))
    generate = Mock(return_value=None)
    monkeypatch.setattr(generator, method, generate)
    auth = {"Authorization": f"Bearer {auth_token}"}
    prefix = "/api/generate"

    def seed(topic):
        content = {"meta": {"grammar_topic": topic}, "questions": ["synthetic"]}
        practice = GeneratedPractice(skill=skill, topic=topic, content=json.dumps(content))
        test_db.add(practice)
        test_db.commit()
        return dict(content, practice_db_id=practice.id)

    calls = 0

    def expect(response, body):
        nonlocal calls
        assert response.status_code == 200
        assert response.json() == body
        calls += 1
        assert generate.call_count == (0 if fixture_app else calls * module.POOL_TARGET)

    first = seed("articles")
    expect(client.get(f"{prefix}/daily-{skill}", headers=auth), {"practices": [first]})

    if skill == "reading":
        # Practice.tsx POSTs this automatically when a learner opens a card.
        expect(client.post(f"{prefix}/trigger-replenish", headers=auth), {"ok": True})

    second = seed("conditionals")
    expect(client.post(f"{prefix}/{more}", headers=auth), {"practices": [second]})
    expect(client.post(f"{prefix}/{more}", headers=auth),
           {"practices": [], "pool_empty": True})

    for card in (first, second):
        expect(client.post(f"{prefix}/submit-ai-{skill}", headers=auth, json={
            "practice_id": card["practice_db_id"], "user_answers": '["synthetic"]',
            "score": 1.0, "correct_count": 1, "total_questions": 1,
        }), {"ok": True})
    expect(client.get(f"{prefix}/daily-{skill}", headers=auth), {"practices": []})

    rows = test_db.query(UserPractice).filter_by(user_id=test_user.id).all()
    assert len(rows) == 2
    assert {row.practice_id for row in rows} == {first["practice_db_id"], second["practice_db_id"]}
    assert all(row.submitted_at and row.user_answers == '["synthetic"]' and row.score == 1.0 for row in rows)
    assert test_db.query(GeneratedPractice).filter_by(skill=skill).count() == 2


def test_writing_keeps_local_prompt_fallback_and_deliberate_review(
    fixture_app, client, test_db, test_user, auth_token, monkeypatch,
):
    monkeypatch.setattr(settings, "STUDY_PASS_ENABLED", True)
    monkeypatch.setattr(settings, "QUOTAS_ENABLED", False)
    replenish = Mock()
    monkeypatch.setattr(writing, "_replenish_writing", replenish)
    fake_grader = Mock()
    fake_grader.grade.return_value = GRADE
    monkeypatch.setattr(writing, "WritingGrader", lambda: fake_grader)
    auth = {"Authorization": f"Bearer {auth_token}"}

    # No fixture is seeded: writing's existing hardcoded bank still deals cards.
    daily = client.get("/api/generate/daily-writing", headers=auth)
    assert daily.status_code == 200
    cards = daily.json()["practices"]
    assert len(cards) == 3
    assert all(card["prompt"]["statement"] for card in cards)
    assert replenish.call_count == (0 if fixture_app else 1)

    # An explicitly requested review is outside the background gate.
    practice_id = cards[0]["practice_db_id"]
    review = client.post("/api/generate/submit-ai-writing", headers=auth, json={
        "practice_id": practice_id, "essay": ESSAY, "time_seconds": 120,
    })
    assert review.status_code == 200
    assert review.json()["grading"] == GRADE
    fake_grader.grade.assert_called_once()
    assert replenish.call_count == (0 if fixture_app else 2)
    row = test_db.query(UserPractice).filter_by(user_id=test_user.id, practice_id=practice_id).one()
    assert row.submitted_at and row.score == 6.5

    more = client.post("/api/generate/generate-more-writing", headers=auth)
    assert more.status_code == 200
    assert more.json()["practices"][0]["prompt"]["statement"]
    assert replenish.call_count == (0 if fixture_app else 3)
