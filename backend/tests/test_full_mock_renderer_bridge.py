"""Pinned renderer-shape examples; no browser, network or production inventory."""
from copy import deepcopy
import pytest

from app.services.full_mock_renderer_bridge import (
    RENDERER_VERSION, RendererBridgeError, renderer_key_map, translate_renderer_answers,
)
from app.services.full_mock_raw_score import score_full_mock
from tests.test_full_mock_audit import fixture


def translate(content, sections, skill):
    return translate_renderer_answers(content, sections, skill=skill, renderer_version=RENDERER_VERSION)


def blank_rows(content):
    return [{"section_number": s["section_number"], "answers": {}} for s in content["sections"]]


@pytest.mark.parametrize("skill", ["reading", "listening"])
@pytest.mark.parametrize("language", ["en", "zh", "ja"])
def test_prompt_language_does_not_change_identities(skill, language):
    content = fixture(skill)
    baseline = renderer_key_map(content, skill=skill, renderer_version=RENDERER_VERSION)
    content["meta"]["topic"] = {"en":"Parcels","zh":"包裹","ja":"荷物"}[language]
    for section in content["sections"]:
        section["meta"] = {"topic": content["meta"]["topic"]}
        rows = section["questions"]["groups"][0]["items"] if skill == "reading" else section["questions"]["completion"]
        for row in rows:
            row["text"] = content["meta"]["topic"] + " ___"
    original = deepcopy(content)
    assert renderer_key_map(content, skill=skill, renderer_version=RENDERER_VERSION) == baseline
    assert content == original
    assert sum(map(len, baseline.values())) == 40


def test_reading_mcq_uses_number_not_index_and_headings_keep_group_namespace():
    content = fixture("reading")
    keys = renderer_key_map(content, skill="reading", renderer_version=RENDERER_VERSION)
    assert keys[1]["q_0_0"] == "s1:q1"
    assert keys[1]["q_1_11"] == "s1:q11"
    assert keys[1]["mh_2_1"] == "s1:heading2:1"
    assert keys[1]["q_0_0"] != keys[2]["q_0_0"]
    rows = blank_rows(content)
    rows[0]["answers"] = {"q_0_0":" BOX ", "mh_2_1":"A", "q_1_11":"A"}
    rows[1]["answers"] = {"q_0_0":"crate"}
    result = translate(content, rows, "reading")
    assert result["answers"]["s1:q1"] == " BOX "
    assert score_full_mock(content, result, skill="reading")["correct"] == 4


def test_listening_matching_precedes_mcq_and_multiple_blocks_each_get_a_group():
    content = fixture("listening")
    questions = content["sections"][0]["questions"]
    original = questions["matching"][0]
    questions["matching"] = [
        {**original, "question_number_end":9, "stems":original["stems"][:1], "answers":{"9":"A"}},
        {**original, "question_number_start":10, "stems":original["stems"][1:], "answers":{"10":"B"}},
    ]
    keys = renderer_key_map(content, skill="listening", renderer_version=RENDERER_VERSION)
    assert keys[1]["q_1_0"] == "s1:q9"
    assert keys[1]["q_2_0"] == "s1:q10"
    assert keys[1]["q_3_0"] == "s1:q8"
    rows = blank_rows(content)
    rows[0]["answers"] = {"q_1_0":"A","q_2_0":"B","q_3_0":"A"}
    assert score_full_mock(content, translate(content, rows, "listening"), skill="listening")["correct"] == 3


def test_keys_only_no_server_answers_in_translation():
    content = fixture("reading")
    content["sections"][0]["questions"]["groups"][0]["items"][0]["answer"] = "PRIVATE_SOLUTION"
    result = translate(content, blank_rows(content), "reading")
    assert result["answers"] == {}
    assert "PRIVATE_SOLUTION" not in str(result)
    assert "PRIVATE_SOLUTION" not in str(renderer_key_map(content, skill="reading", renderer_version=RENDERER_VERSION))


@pytest.mark.parametrize("bad", ["duplicate_section","missing_section","unknown_section","bool_section",
                                "unknown_key","audit_key","nonstring","extra_field","nonlist"])
def test_bad_envelopes_fail_closed(bad):
    content = fixture("reading")
    rows = blank_rows(content)
    if bad == "duplicate_section": rows[1]["section_number"] = 1
    if bad == "missing_section": rows.pop()
    if bad == "unknown_section": rows[0]["section_number"] = 8
    if bad == "bool_section": rows[0]["section_number"] = True
    if bad == "unknown_key": rows[0]["answers"]["q_99_0"] = "A"
    if bad == "audit_key": rows[0]["answers"]["s1:q1"] = "A"
    if bad == "nonstring": rows[0]["answers"]["q_0_0"] = ["A"]
    if bad == "extra_field": rows[0]["practice_id"] = 1
    if bad == "nonlist": rows = {}
    with pytest.raises(RendererBridgeError):
        translate(content, rows, "reading")


@pytest.mark.parametrize("kind", ["summary_completion","matching_information"])
def test_unproven_renderability_is_not_guessed(kind):
    content = fixture("reading")
    group = content["sections"][0]["questions"]["groups"][0]
    group["type"] = kind
    group["summary_text"] = " ".join(f"___{i['question_number']}___" for i in group["items"])
    for item in group["items"]: item["statement"] = "An original statement"
    with pytest.raises(RendererBridgeError):
        translate(content, blank_rows(content), "reading")


def test_renderer_version_must_be_explicit():
    with pytest.raises(RendererBridgeError):
        renderer_key_map(fixture("reading"), skill="reading", renderer_version="v1")


def test_same_heading_paragraph_number_in_different_groups_does_not_collide():
    content = fixture("reading")
    groups = content["sections"][0]["questions"]["groups"]
    heading = groups.pop()
    for answer in ("A", "B"):
        split = deepcopy(heading)
        split["items"]["paragraphs"] = [{"number":1,"title":"Original paragraph"}]
        split["answers"] = [{"paragraph_number":1,"answer":answer}]
        groups.append(split)
    keys = renderer_key_map(content, skill="reading", renderer_version=RENDERER_VERSION)
    assert keys[1]["mh_2_1"] == "s1:heading2:1"
    assert keys[1]["mh_3_1"] == "s1:heading3:1"


def test_empty_listening_group_does_not_consume_a_renderer_index():
    content = fixture("listening")
    q = content["sections"][0]["questions"]
    q["multiple_choice"] += [
        {"question_number":item["question_number"],"question":"Original choice",
         "options":{"A":"Red","B":"Blue"},"answer":"A"}
        for item in q["completion"]
    ]
    q["completion"] = []
    keys = renderer_key_map(content, skill="listening", renderer_version=RENDERER_VERSION)
    assert keys[1]["q_0_0"] == "s1:q9"
    assert keys[1]["q_1_0"] == "s1:q8"


@pytest.mark.parametrize("bad", ["question_number","paragraph_number"])
def test_duplicate_audit_identities_never_translate(bad):
    content = fixture("reading")
    groups = content["sections"][0]["questions"]["groups"]
    if bad == "question_number":
        groups[0]["items"][1]["question_number"] = 1
    else:
        groups[2]["items"]["paragraphs"][1]["number"] = 1
    with pytest.raises(ValueError):
        translate(content, blank_rows(content), "reading")
