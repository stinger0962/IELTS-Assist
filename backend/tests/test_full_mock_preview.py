"""Synthetic field-separation tests, not assertions of semantic answer secrecy."""
from copy import deepcopy
import json
import pytest

from app.services.full_mock_audit import audit_full_mock
from app.services.full_mock_renderer_bridge import RENDERER_VERSION, RendererBridgeError
from app.services.full_mock_preview import PREVIEW_VERSION, PreviewShapeError, active_mock_preview
from tests.test_full_mock_audit import fixture


def preview(content, skill):
    return active_mock_preview(content, skill=skill, renderer_version=RENDERER_VERSION)


@pytest.mark.parametrize("skill", ["reading", "listening"])
def test_only_explicit_public_fields_and_no_nested_private_passthrough(skill):
    content = fixture(skill)
    marker = "PRIVATE_SENTINEL_NOT_FOR_CLIENT"
    # Options/answer maps have exact meaningful keys and cannot receive arbitrary
    # properties without changing the validated content. Inject other nested nodes.
    content["private_debug"] = marker
    content["meta"]["private_debug"] = marker
    for section in content["sections"]:
        section["private_debug"] = marker
        section["meta"] = {"private_debug": marker}
        if skill == "reading":
            section["passage"] = {"content": "Original public reading passage.", "private_debug": marker}
            for group in section["questions"]["groups"]:
                group["explanation"] = marker
                items = group["items"]
                if isinstance(items, list):
                    for item in items:
                        item["explanation"] = item["feedback"] = marker
                    items[0]["private_debug"] = marker
                else:
                    items["private_debug"] = marker
                    for h in items["headings"]: h["explanation"] = marker
                    for p in items["paragraphs"]: p["feedback"] = marker
            section["questions"]["groups"][0]["items"][0]["answer"] = marker
        else:
            section["transcript"] = marker
            for item in section["questions"]["completion"]:
                item["explanation"] = item["feedback"] = marker
            section["questions"]["completion"][0]["answer"] = marker
            for block in section["questions"]["matching"]:
                block["private_debug"] = marker
                for stem in block["stems"]: stem["feedback"] = marker
    before = deepcopy(content)
    result = preview(content, skill)
    encoded = json.dumps(result)
    assert marker not in encoded
    assert all(field not in encoded for field in ('"answer"', '"answers"', '"transcript"', '"explanation"', '"feedback"', '"meta"'))
    assert content == before
    assert set(result) == {"schema_version","skill","total_questions","sections"}
    assert result["schema_version"] == PREVIEW_VERSION
    assert {q["key"] for s in result["sections"] for q in s["questions"]} == {
        item.key for item in audit_full_mock(content, skill=skill)}
    # Output nested structures are detached: downstream mutation cannot mutate history.
    result["sections"][0]["questions"][0]["prompt"] = "Changed"
    assert content == before


@pytest.mark.parametrize("skill", ["reading", "listening"])
def test_options_are_labels_only_and_nested_questions_remain_individual(skill):
    result = preview(fixture(skill), skill)
    questions = [q for section in result["sections"] for q in section["questions"]]
    assert len(questions) == 40
    nested = [q for q in questions if q["type"] in ("matching","matching_headings")]
    assert len(nested) == (6 if skill == "reading" else 8)
    assert nested[0]["options"] == (
        [{"id":"A","text":"Delivery"},{"id":"B","text":"Return"}] if skill == "reading" else
        [{"id":"A","text":"Red"},{"id":"B","text":"Blue"}])
    for question in questions:
        assert set(question) <= {"key","type","prompt","options","word_limit"}


@pytest.mark.parametrize("url", [
    "https://unapproved.example/answer.mp3", "/audio/file.mp3?token=private",
    "/audio/../private.mp3", "/audio/%2e%2e/private.mp3", "data:audio/wav;base64,secret",
    "//elsewhere.example/audio.wav", "/audio/file.mp3#private", "/audio/name.wav/secret",
])
def test_uncontrolled_audio_reference_rejected(url):
    content = fixture("listening")
    content["sections"][0]["audio_url"] = url
    with pytest.raises(PreviewShapeError): preview(content, "listening")


@pytest.mark.parametrize("limit", [True, 0, -1, "3", {"answer":"private"}])
def test_invalid_word_limit_not_copied(limit):
    content = fixture("reading")
    content["sections"][0]["questions"]["groups"][0]["items"][0]["word_limit"] = limit
    with pytest.raises(PreviewShapeError): preview(content, "reading")


def test_explicit_word_limit_and_multilingual_prompt_preserved():
    content = fixture("reading")
    item = content["sections"][0]["questions"]["groups"][0]["items"][0]
    item.update(text="包裹 / 荷物 ___", word_limit=3)
    first = preview(content, "reading")["sections"][0]["questions"][0]
    assert first["prompt"] == "包裹 / 荷物 ___"
    assert first["word_limit"] == 3


def test_unreviewed_renderer_version_rejected():
    with pytest.raises(RendererBridgeError):
        active_mock_preview(fixture("reading"), skill="reading", renderer_version="new")


def test_private_properties_inside_option_map_are_rejected_not_forwarded():
    content = fixture("reading")
    options = content["sections"][0]["questions"]["groups"][1]["items"][0]["options"]
    options["private_debug"] = "PRIVATE_OPTION_METADATA"
    with pytest.raises(PreviewShapeError):
        preview(content, "reading")


def test_private_properties_in_heading_identity_are_rejected():
    content = fixture("reading")
    group = content["sections"][0]["questions"]["groups"][2]
    group["items"]["headings"][0]["id"] = "PRIVATE_HEADING_ID"
    group["answers"][0]["answer"] = "PRIVATE_HEADING_ID"
    with pytest.raises(PreviewShapeError):
        preview(content, "reading")
