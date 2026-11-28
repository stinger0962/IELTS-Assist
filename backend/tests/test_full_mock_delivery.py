"""Original synthetic fixtures: delivery contracts, not exam quality or deployed audio."""
import json
import math
import socket
import struct
import wave

import pytest
from starlette.staticfiles import StaticFiles
from app.config import settings
from app.main import app
from app.models.models import GeneratedPractice, UserPractice
from app.routers import reading, listening
from app.staging import _load_fixture_app
from app.services.study_pass import grant_study_pass


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(settings, "STUDY_PASS_ENABLED", True)
    monkeypatch.setattr(settings, "DAILY_GENERATION_ENABLED", False)
    monkeypatch.setattr(app, "state", type(app.state)())
    assert _load_fixture_app() is app

    def forbidden(*args, **kwargs):
        raise AssertionError("External network/provider/scheduler is forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr("app.main.AsyncIOScheduler", forbidden)
    # pytest.fail raises a BaseException, not swallowed by the worker's logging.
    def no_refill(*args, **kwargs):
        pytest.fail("fixture full mocks must not enqueue background replenishment")

    monkeypatch.setattr(reading, "_replenish", no_refill)
    monkeypatch.setattr(listening, "_replenish_listening", no_refill)


def original_exam(skill):
    sections = []
    for number in range(1, 4 if skill == "reading" else 5):
        facts = [f"Station {i + 1} stores parcel{i + 1}." for i in range(10)]
        items = [{"text": f"Station {i + 1} stores ____.", "answer": f"parcel{i + 1}"}
                 for i in range(10)]
        section = {"section_number": number, "question_count": 10,
                   "meta": {"topic": f"Original station tour {number}"}}
        if skill == "reading":
            section.update(passage={"title": f"Station tour {number}", "content": " ".join(facts)},
                           questions={"groups": [{"type": "sentence_completion", "items": items}]})
        else:
            section.update(format=["conversation", "monologue", "discussion", "lecture"][number - 1],
                           description="Synthetic delivery fixture, not an IELTS exam",
                           transcript="Guide: " + " ".join(facts),
                           audio_url="/audio/fixture-tone.wav", questions={"completion": items})
        sections.append(section)
    return {"meta": {"module": f"{skill}_full_test", "topic": "Original delivery fixture",
                     "total_questions": len(sections) * 10,
                     "time_limit_minutes": 60 if skill == "reading" else 30, "version": "v1"},
            "sections": sections}


@pytest.fixture
def local_audio(tmp_path):
    # Controlled test mount only: actual FastAPI app does NOT mount /audio.
    filename = tmp_path / "fixture-tone.wav"
    with wave.open(str(filename), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"".join(struct.pack("<h", int(1000 * math.sin(i * 2 * math.pi * 440 / 8000)))
                                 for i in range(800)))
    app.mount("/audio", StaticFiles(directory=tmp_path), name="fixture-audio-only")
    mount = app.routes[-1]
    try:
        yield filename
    finally:
        app.router.routes.remove(mount)


@pytest.mark.parametrize("skill,total", [("reading", 30), ("listening", 40)])
def test_paid_full_mock_delivery(client, test_db, test_user, auth_token, local_audio, skill, total):
    headers = {"Authorization": f"Bearer {auth_token}"}
    grant_study_pass(test_db, test_user.id, "fixture:offline-pass", 2)
    exercise = original_exam(skill)
    practice = GeneratedPractice(skill=skill, topic="Original delivery fixture",
                                 content=json.dumps(exercise), is_validated=True)
    test_db.add(practice)
    test_db.commit()
    assert client.get("/api/study-pass", headers=headers).json()["full_mock_access"] is True
    path = f"/api/generate/daily-{skill}"
    assert client.get(path).status_code == 401
    for _ in range(2):
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        cards = response.json()["practices"]
        assert cards == [dict(exercise, practice_db_id=practice.id)]
    assignment = test_db.query(UserPractice).filter_by(user_id=test_user.id, practice_id=practice.id)
    assert assignment.count() == 1
    assert assignment.one().submitted_at is None
    # Full payload is available to the opening view; not a browser rendering test.
    if skill == "listening":
        for section in cards[0]["sections"]:
            audio = client.get(section["audio_url"])
            assert audio.status_code == 200
            assert audio.headers["content-type"] in ("audio/wav", "audio/x-wav")
            assert audio.content[:4] == b"RIFF" and audio.content[8:12] == b"WAVE"
            assert audio.content == local_audio.read_bytes()
    body = {"practice_id": practice.id, "time_taken_seconds": 42,
            "sections": [{"section_number": section["section_number"],
                          "answers": {f"q_0_{i}": f"parcel{i + 1}" for i in range(10)}}
                         for section in exercise["sections"]]}
    submission = f"/api/generate/submit-ai-{skill}-exam"
    response = client.post(submission, headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["overall"] == {"correct": total, "total": total, "band": 8.5}
    test_db.expire_all()
    assert assignment.one().submitted_at is not None
    assert assignment.one().correct_count == total
    assert client.post(submission, headers=headers, json=body).status_code == 404
    history = client.get(f"/api/generate/recent-exams?skill={skill}", headers=headers).json()
    assert len(history) == 1 and history[0]["exercise"] == exercise
    assert history[0]["result"] == response.json()
    assert client.get(path, headers=headers).json()["practices"] == []


def test_pass_does_not_create_missing_inventory(client, test_db, test_user, auth_token):
    grant_study_pass(test_db, test_user.id, "fixture:empty-pool-pass", 2)
    test_db.commit()
    headers = {"Authorization": f"Bearer {auth_token}"}
    assert client.get("/api/study-pass", headers=headers).json()["full_mock_access"] is True
    for skill in ("reading", "listening"):
        assert client.get(f"/api/generate/daily-{skill}", headers=headers).json() == {"practices": []}
    assert test_db.query(GeneratedPractice).count() == 0
