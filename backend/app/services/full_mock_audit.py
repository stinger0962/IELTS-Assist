"""Pure, opt-in structural QA; never admits inventory or changes v1 scoring.

Keys below are audit identities, NOT legacy renderer/submission keys. A pass
does not certify answer correctness, text length, difficulty, audio or IELTS
equivalence. No DB, settings, provider, routing or filesystem imports.
"""
from dataclasses import dataclass
import re


class MockStructureError(ValueError):
    pass


@dataclass(frozen=True)
class AuditItem:
    section: int
    key: str
    question_type: str
    answers: tuple[str, ...]


def _require(condition, message):
    if not condition:
        raise MockStructureError(message)


def _mapping(value):
    _require(isinstance(value, dict), "Expected an object")
    return value


def _list(value, *, empty=False):
    _require(isinstance(value, list) and (empty or bool(value)), "Expected a list")
    return value


def _number(value):
    _require(type(value) is int and 1 <= value <= 40, "Expected an integer identity in 1–40")
    return value


def _text(value):
    _require(isinstance(value, str) and bool(value.strip()), "Missing text")
    return value.strip()


def _answers(value):
    values = value if isinstance(value, list) else [value]
    _require(bool(values), "Missing answer")
    return tuple(_text(v) for v in values)


def _options(value):
    options = _mapping(value)
    _require(len(options) >= 2, "Missing options")
    for key, text in options.items():
        _text(key)
        _text(text)
    return set(options)


def _item(item, kind, section, *, summary=None):
    item = _mapping(item)
    number = _number(item.get("question_number"))
    answers = _answers(item.get("answer"))
    if kind == "summary_completion":
        _text(summary)
        _require(f"___{number}___" in summary, "Missing summary input placeholder")
    else:
        field = {
            "true_false_not_given": "statement", "yes_no_not_given": "statement",
            "matching_information": "statement", "multiple_choice": "question",
            "short_answer": "question", "sentence_completion": "text",
            "completion": "text",
        }[kind]
        _text(item.get(field))
    if kind == "multiple_choice":
        _require(set(answers) <= _options(item.get("options")), "Answer outside options")
    if kind in ("true_false_not_given", "yes_no_not_given"):
        choices = {"TRUE", "FALSE", "NOT GIVEN"} if kind == "true_false_not_given" else {"YES", "NO", "NOT GIVEN"}
        _require(set(answers) <= choices, "Invalid judgement answer")
    return AuditItem(section, f"s{section}:q{number}", kind, answers)


def _reading(section, number):
    passage = section.get("passage")
    _text(passage.get("content") if isinstance(passage, dict) else passage)
    groups = _list(_mapping(section.get("questions")).get("groups"))
    result = []
    supported = {"true_false_not_given", "yes_no_not_given", "multiple_choice",
                 "short_answer", "sentence_completion", "summary_completion",
                 "matching_information"}
    for gi, group in enumerate(groups):
        group = _mapping(group)
        kind = group.get("type")
        _require(isinstance(kind, str), "Missing question type")
        if kind == "matching_headings":
            items = _mapping(group.get("items"))
            headings = _list(items.get("headings"))
            choices = [_text(_mapping(h).get("id")) for h in headings]
            _require(len(set(choices)) == len(choices), "Duplicate heading option")
            for h in headings:
                _text(h.get("text"))
            paragraphs = _list(items.get("paragraphs"))
            ids = [_number(_mapping(p).get("number")) for p in paragraphs]
            _require(len(set(ids)) == len(ids), "Duplicate paragraph identity")
            answer_rows = _list(group.get("answers"))
            answer_ids = [_number(_mapping(a).get("paragraph_number")) for a in answer_rows]
            _require(len(answer_ids) == len(set(answer_ids)) and set(answer_ids) == set(ids),
                     "Heading inputs and answer identities differ")
            by_id = {a["paragraph_number"]: _answers(a.get("answer")) for a in answer_rows}
            for paragraph in paragraphs:
                _text(paragraph.get("title"))
                pid = paragraph["number"]
                _require(set(by_id[pid]) <= set(choices), "Answer outside headings")
                result.append(AuditItem(number, f"s{number}:heading{gi}:{pid}", kind, by_id[pid]))
        else:
            _require(kind in supported, "Unsupported reading question type")
            result.extend(_item(i, kind, number, summary=group.get("summary_text"))
                          for i in _list(group.get("items")))
    return result


def _listening(section, number):
    _text(section.get("transcript"))
    _text(section.get("audio_url"))
    questions = _mapping(section.get("questions"))
    _require(bool(questions) and set(questions) <= {"completion", "multiple_choice", "matching"},
             "Unsupported listening question shape")
    result = []
    for kind in ("completion", "multiple_choice"):
        result.extend(_item(i, kind, number) for i in _list(questions.get(kind, []), empty=True))
    for block in _list(questions.get("matching", []), empty=True):
        block = _mapping(block)
        stems = _list(block.get("stems"))
        ids = [_number(_mapping(stem).get("question_number")) for stem in stems]
        _require(len(ids) == len(set(ids)), "Duplicate matching stem")
        start = _number(block.get("question_number_start"))
        end = _number(block.get("question_number_end"))
        _require(ids == list(range(start, end + 1)), "Matching range differs from stems")
        choices = []
        for option in _list(block.get("options")):
            match = re.fullmatch(r"([A-Z])\.\s+(.+)", _text(option))
            _require(match is not None, "Unsupported matching option label")
            choices.append(match[1])
        _require(len(choices) >= 2 and len(choices) == len(set(choices)), "Duplicate/missing options")
        answers = _mapping(block.get("answers"))
        _require(set(answers) == {str(i) for i in ids}, "Matching inputs and answers differ")
        for stem in stems:
            _text(stem.get("text"))
            qid = stem["question_number"]
            values = _answers(answers[str(qid)])
            _require(set(values) <= set(choices), "Answer outside matching options")
            result.append(AuditItem(number, f"s{number}:q{qid}", "matching", values))
    return result


def audit_full_mock(content, *, skill):
    """Return 40 immutable leaf identities, or raise MockStructureError.

    Explicit invocation only. Version metadata is left untouched; this audit
    may diagnose legacy payloads but never relabels them as v2/eligible inventory.
    """
    _require(skill in ("reading", "listening"), "Unsupported skill")
    content = _mapping(content)
    meta = _mapping(content.get("meta"))
    _require(meta.get("module") == f"{skill}_full_test", "Wrong full-mock module")
    _require(type(meta.get("total_questions")) is int and meta["total_questions"] == 40,
             "Declared full-mock total must be 40")
    sections = _list(content.get("sections"))
    _require(len(sections) == (3 if skill == "reading" else 4), "Wrong section count")
    leaves = []
    for expected, section in enumerate(sections, 1):
        section = _mapping(section)
        _require(_number(section.get("section_number")) == expected, "Sections must be unique and ordered")
        items = (_reading if skill == "reading" else _listening)(section, expected)
        _require(type(section.get("question_count")) is int and section["question_count"] == len(items),
                 "Declared section count differs from answerable leaves")
        _require(skill != "listening" or len(items) == 10, "Listening part must have ten leaves")
        leaves.extend(items)
    _require(len(leaves) == 40, "Full mock must have forty answerable leaves")
    _require(len({i.key for i in leaves}) == 40, "Duplicate answerable identity")
    return tuple(leaves)
