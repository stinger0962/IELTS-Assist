"""Original synthetic structural fixtures, not pedagogic quality examples."""
from copy import deepcopy
import pytest

from app.services.full_mock_audit import audit_full_mock, MockStructureError


def fixture(skill):
    sections = []
    for sn, count in enumerate([13, 13, 14] if skill == "reading" else [10] * 4, 1):
        section = dict(section_number=sn, question_count=count)
        completion = [dict(question_number=i, text=f"Parcel {i}: ___", answer=["box", "crate"])
                      for i in range(1, count - 2)]
        choice = dict(question_number=count-2, question="Which parcel?", options={"A":"Red","B":"Blue"}, answer="A")
        if skill == "reading":
            section.update(passage="An original synthetic parcel account.", questions={"groups":[
                {"type":"sentence_completion", "items":completion},
                {"type":"multiple_choice", "items":[choice]},
                {"type":"matching_headings", "items":{
                    "headings":[{"id":"A","text":"Delivery"},{"id":"B","text":"Return"}],
                    "paragraphs":[{"number":1,"title":"Morning"},{"number":2,"title":"Evening"}]},
                 "answers":[{"paragraph_number":1,"answer":"A"},{"paragraph_number":2,"answer":"B"}]}
            ]})
        else:
            section.update(transcript="Guide: Parcel delivery example.", audio_url="/audio/synthetic.wav",
                questions={"completion":completion, "multiple_choice":[choice], "matching":[{
                    "question_number_start":9, "question_number_end":10,
                    "stems":[{"question_number":9,"text":"First parcel"},{"question_number":10,"text":"Second parcel"}],
                    "options":["A. Red","B. Blue"], "answers":{"9":"A","10":"B"}}]})
        sections.append(section)
    return {"meta":{"module":f"{skill}_full_test","total_questions":40,"version":"v1"}, "sections":sections}


@pytest.mark.parametrize("skill", ["reading","listening"])
def test_exact_leaf_counts_nonmutating_and_alternatives(skill):
    content = fixture(skill)
    before = deepcopy(content)
    items = audit_full_mock(content, skill=skill)
    assert len(items) == len({item.key for item in items}) == 40
    assert items[0].answers == ("box", "crate")
    assert content == before
    assert [sum(i.section == n for i in items) for n in range(1,len(content["sections"])+1)] == (
        [13,13,14] if skill == "reading" else [10]*4)


@pytest.mark.parametrize("skill", ["reading","listening"])
@pytest.mark.parametrize("bad", ["declared", "section_order", "missing_section", "count", "bool_count", "empty_answer", "duplicate", "missing_content"])
def test_rejects_structural_mismatch(skill, bad):
    content = fixture(skill)
    section = content["sections"][0]
    rows = section["questions"]["groups"][0]["items"] if skill == "reading" else section["questions"]["completion"]
    if bad == "declared": content["meta"]["total_questions"] = 39
    if bad == "section_order": section["section_number"] = 2
    if bad == "missing_section": content["sections"].pop()
    if bad == "count": section["question_count"] -= 1
    if bad == "bool_count": section["question_count"] = True
    if bad == "empty_answer": rows[0]["answer"] = []
    if bad == "duplicate": rows[1]["question_number"] = rows[0]["question_number"]
    if bad == "missing_content": section["passage" if skill == "reading" else "audio_url"] = ""
    with pytest.raises(MockStructureError):
        audit_full_mock(content, skill=skill)


@pytest.mark.parametrize("delta", [-1, 1])
def test_actual_39_or_41_rejected_despite_declared_40(delta):
    content = fixture("reading")
    section = content["sections"][0]
    rows = section["questions"]["groups"][0]["items"]
    if delta < 0: rows.pop()
    else: rows.append(dict(question_number=39,text="Extra ___",answer="one"))
    section["question_count"] += delta
    with pytest.raises(MockStructureError):
        audit_full_mock(content, skill="reading")


def test_listening_nine_eleven_not_a_complete_mock():
    content = fixture("listening")
    a,b = content["sections"][:2]
    item = a["questions"]["completion"].pop()
    item["question_number"] = 99
    b["questions"]["completion"].append(item)
    a["question_count"] -= 1
    b["question_count"] += 1
    with pytest.raises(MockStructureError):
        audit_full_mock(content, skill="listening")


@pytest.mark.parametrize("bad", ["orphan", "missing", "duplicate", "option"])
def test_heading_answers_must_have_rendered_input(bad):
    content = fixture("reading")
    group = content["sections"][0]["questions"]["groups"][2]
    if bad == "orphan": group["answers"].append(dict(paragraph_number=3,answer="A"))
    if bad == "missing": group["answers"].pop()
    if bad == "duplicate": group["items"]["paragraphs"][1]["number"] = 1
    if bad == "option": group["answers"][0]["answer"] = "Z"
    with pytest.raises(MockStructureError):
        audit_full_mock(content, skill="reading")


@pytest.mark.parametrize("bad", ["range", "missing", "orphan", "option", "duplicate"])
def test_nested_matching_inputs_and_answers_agree(bad):
    content = fixture("listening")
    block = content["sections"][0]["questions"]["matching"][0]
    if bad == "range": block["question_number_end"] = 11
    if bad == "missing": del block["answers"]["10"]
    if bad == "orphan": block["answers"]["11"] = "A"
    if bad == "option": block["answers"]["9"] = "Z"
    if bad == "duplicate": block["options"] = ["A. Red","A. Blue"]
    with pytest.raises(MockStructureError):
        audit_full_mock(content, skill="listening")


@pytest.mark.parametrize("skill", ["reading","listening"])
def test_unsupported_shapes_not_silently_ignored(skill):
    content = fixture(skill)
    q = content["sections"][0]["questions"]
    if skill == "reading": q["groups"][0]["type"] = "invented"
    else: q["groups"] = [{"type":"completion","items":[]}]
    with pytest.raises(MockStructureError):
        audit_full_mock(content, skill=skill)


@pytest.mark.parametrize("kind,field,answer", [
    ("true_false_not_given","statement","TRUE"), ("yes_no_not_given","statement","NOT GIVEN"),
    ("short_answer","question","box"), ("matching_information","statement","A"),
    ("summary_completion",None,"box"),
])
def test_other_supported_reading_leaf_shapes(kind, field, answer):
    content = fixture("reading")
    group = content["sections"][0]["questions"]["groups"][0]
    group["type"] = kind
    group["summary_text"] = " ".join(f"___{i['question_number']}___" for i in group["items"])
    for item in group["items"]:
        item["answer"] = answer
        if field: item[field] = "An original prompt"
    assert len(audit_full_mock(content, skill="reading")) == 40


def test_summary_answer_without_placeholder_is_rejected():
    content = fixture("reading")
    group = content["sections"][0]["questions"]["groups"][0]
    group.update(type="summary_completion", summary_text="There is no input.")
    with pytest.raises(MockStructureError):
        audit_full_mock(content, skill="reading")


def test_pure_import_does_not_load_application_or_database(tmp_path):
    import os
    from pathlib import Path
    import subprocess
    import sys
    env = {**os.environ, "PYTHONPATH":str(Path(__file__).resolve().parents[1])}
    result = subprocess.run([sys.executable, "-c",
        "import sys; import app.services.full_mock_audit; "
        "assert not {'app.database','app.main','app.config','sqlalchemy'} & sys.modules.keys()"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
