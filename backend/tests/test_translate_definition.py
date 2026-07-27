"""Vocabulary definition translation.

Replaced the Youdao Smart Cloud integration (HMAC-signed request, two extra
credentials) with a utility-tier model call. The model also sees the word
itself, so it can disambiguate — Youdao translated the definition blind.
"""

import json

import app.routers.generate as gen

PAYLOAD = {"word": "bank", "content_en": "the land alongside a river or lake"}
PATH = "/api/generate/translate-definition"


def test_returns_the_chinese_translation(client, test_user, auth_token, monkeypatch):
    captured = {}

    def fake_chat_json(**kwargs):
        captured.update(kwargs)
        return json.dumps({"content_zh": "河岸；湖岸"})

    monkeypatch.setattr(gen, "chat_json", fake_chat_json)

    resp = client.post(PATH, json=PAYLOAD, headers={"Authorization": f"Bearer {auth_token}"})

    assert resp.status_code == 200
    assert resp.json()["content_zh"] == "河岸；湖岸"
    assert captured["tier"] == "utility"
    # The word must reach the model, otherwise it cannot disambiguate "bank".
    assert "bank" in json.dumps(captured["messages"], ensure_ascii=False)


def test_degrades_to_empty_string_when_the_model_fails(
    client, test_user, auth_token, monkeypatch
):
    """The UI treats "" as 'no translation available' and still shows the English."""

    def boom(**kwargs):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(gen, "chat_json", boom)

    resp = client.post(PATH, json=PAYLOAD, headers={"Authorization": f"Bearer {auth_token}"})

    assert resp.status_code == 200
    assert resp.json()["content_zh"] == ""


def test_requires_authentication(client):
    assert client.post(PATH, json=PAYLOAD).status_code == 401
