"""Offline regression coverage for the Listening validation/synthesis boundary."""
from importlib import import_module
from unittest.mock import Mock

import pytest

generator_module = import_module("app.services.ai.listening_generator")


@pytest.fixture
def pipeline(monkeypatch):
    generator = generator_module.ListeningGenerator()
    metadata = Mock(side_effect=[{"accent": f"accent-{i}"} for i in range(4)])
    monkeypatch.setattr(generator_module, "generate_metadata", metadata)
    transcript = Mock(return_value={"transcript": "Example rehearsal text."})
    questions = Mock(side_effect=lambda meta, _transcript: {"meta": {"candidate": meta["accent"]}})
    validation = Mock()
    synthesize = Mock(return_value="/test/audio.mp3")
    monkeypatch.setattr(generator, "_generate_transcript", transcript)
    monkeypatch.setattr(generator, "_generate_questions", questions)
    monkeypatch.setattr(generator, "_validate", validation)
    monkeypatch.setattr(generator, "_synthesize_audio", synthesize)
    return generator, transcript, questions, validation, synthesize


@pytest.mark.parametrize("verdict", [{"valid": False}, {"valid": "false"}, {}])
def test_rejected_candidates_never_reach_tts(pipeline, verdict):
    generator, transcript, questions, validation, synthesize = pipeline
    validation.return_value = verdict

    assert generator.generate() is None
    assert transcript.call_count == questions.call_count == validation.call_count == 4
    synthesize.assert_not_called()


def test_missing_retry_transcripts_cannot_reuse_rejected_candidate(pipeline):
    generator, transcript, questions, validation, synthesize = pipeline
    transcript.side_effect = [{"transcript": "Example rehearsal text."}, None, None, None]
    validation.return_value = {"valid": False}

    assert generator.generate() is None
    assert transcript.call_count == 4
    assert questions.call_count == validation.call_count == 1
    synthesize.assert_not_called()


@pytest.mark.parametrize("rejects", [0, 1, 3])
def test_only_the_passing_candidate_is_synthesized(pipeline, rejects):
    generator, _, _, validation, synthesize = pipeline
    validation.side_effect = [{"valid": False}] * rejects + [{"valid": True}]

    result = generator.generate()

    assert result == {
        "meta": {
            "candidate": f"accent-{rejects}",
            "accent": f"accent-{rejects}",
            "audio_url": "/test/audio.mp3",
        }
    }
    assert validation.call_count == rejects + 1
    synthesize.assert_called_once_with(result)


def test_full_mock_is_not_assembled_if_first_section_never_validates(monkeypatch):
    exam_module = import_module("app.services.ai.listening_exam")
    generator = generator_module.ListeningGenerator()
    monkeypatch.setattr(exam_module, "ListeningGenerator", lambda: generator)
    monkeypatch.setattr(generator_module, "generate_metadata", lambda **_: {"accent": "mock"})
    monkeypatch.setattr(generator, "_generate_transcript", lambda _: {"transcript": "Practice transcript."})
    monkeypatch.setattr(generator, "_generate_questions", lambda *_: {"meta": {"topic": "Fixture"}})
    verdict = Mock(return_value={"valid": False})
    synthesize = Mock()
    monkeypatch.setattr(generator, "_validate", verdict)
    monkeypatch.setattr(generator, "_synthesize_audio", synthesize)

    assert exam_module.generate_listening_exam() is None
    assert verdict.call_count == 12  # three section calls, four candidates each
    synthesize.assert_not_called()
