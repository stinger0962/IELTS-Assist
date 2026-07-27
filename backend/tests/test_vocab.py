import json

import pytest

from app.services import vocab


def test_parse_returns_all_fields():
    raw = json.dumps(
        {
            "definition_en": "to increase the strength of something",
            "definition_zh": "放大；增强",
            "example": "The hall amplified every footstep.",
            "phonetic": "/ˈæmplɪfaɪ/",
        }
    )
    parsed = vocab.parse_lookup(raw)
    assert parsed["definition_en"].startswith("to increase")
    assert parsed["definition_zh"] == "放大；增强"
    assert parsed["phonetic"] == "/ˈæmplɪfaɪ/"


def test_parse_tolerates_missing_optional_fields():
    parsed = vocab.parse_lookup(json.dumps({"definition_en": "a thing"}))
    assert parsed["definition_en"] == "a thing"
    assert parsed["definition_zh"] is None
    assert parsed["phonetic"] is None


def test_parse_rejects_a_missing_definition():
    with pytest.raises(ValueError):
        vocab.parse_lookup(json.dumps({"phonetic": "/x/"}))


def test_normalise_word():
    assert vocab.normalise("  Amplify  ") == "amplify"
    assert vocab.normalise("RIVER") == "river"


# ── Endpoint behaviour ───────────────────────────────────────────────────────

def test_define_word_caches_after_first_call(client, test_user, auth_token, monkeypatch):
    calls = []

    def fake_generate(word, context=None):
        calls.append(word)
        return {
            "definition_en": "the land alongside a river",
            "definition_zh": "河岸",
            "example": "We sat on the bank.",
            "phonetic": "/bæŋk/",
        }

    monkeypatch.setattr(vocab, "generate_entry", fake_generate)
    monkeypatch.setattr(vocab, "synthesize_pronunciation", lambda w: "/audio/bank.mp3")

    h = {"Authorization": f"Bearer {auth_token}"}
    first = client.post("/api/generate/define-word", json={"word": "Bank"}, headers=h)
    second = client.post("/api/generate/define-word", json={"word": "bank"}, headers=h)

    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert first.json()["audio_url"] == "/audio/bank.mp3"
    # Different casing must hit the same cache row.
    assert second.json()["cached"] is True
    assert second.json()["definition_zh"] == "河岸"
    assert len(calls) == 1, "second lookup must not hit the model"


def test_define_word_survives_tts_failure(client, test_user, auth_token, monkeypatch):
    """Audio is a nice-to-have; losing it must not lose the definition."""
    monkeypatch.setattr(vocab, "generate_entry", lambda w, c=None: {
        "definition_en": "x", "definition_zh": None, "example": None, "phonetic": None})
    monkeypatch.setattr(vocab, "synthesize_pronunciation", lambda w: None)

    resp = client.post("/api/generate/define-word", json={"word": "zzz"},
                       headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    assert resp.json()["audio_url"] is None
    assert resp.json()["definition_en"] == "x"


def test_define_word_reports_upstream_failure(client, test_user, auth_token, monkeypatch):
    def boom(word, context=None):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(vocab, "generate_entry", boom)
    resp = client.post("/api/generate/define-word", json={"word": "qqq"},
                       headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 502


def test_define_word_requires_auth(client):
    assert client.post("/api/generate/define-word", json={"word": "x"}).status_code == 401


def test_translate_returns_chinese(client, test_user, auth_token, monkeypatch):
    """General EN->ZH, used for grammar tips. Kept separate from define-word."""
    import app.routers.generate as gen
    monkeypatch.setattr(gen, "chat_json", lambda **kw: json.dumps({"text_zh": "被动语态"}))

    resp = client.post("/api/generate/translate", json={"text": "the passive voice"},
                       headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    assert resp.json()["text_zh"] == "被动语态"


def test_translate_degrades_to_empty_string(client, test_user, auth_token, monkeypatch):
    import app.routers.generate as gen
    def boom(**kw):
        raise RuntimeError("down")
    monkeypatch.setattr(gen, "chat_json", boom)

    resp = client.post("/api/generate/translate", json={"text": "x"},
                       headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    assert resp.json()["text_zh"] == ""
