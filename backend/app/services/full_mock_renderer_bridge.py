"""Opt-in identity bridge for a narrow, pinned full-test renderer contract.

Does not sanitize content, accept legacy scorer semantics, certify renderability,
or wire a route. Requires the private answer-bearing payload for structural
audit; never return that payload or audit answer definitions to a client.
"""
from .full_mock_audit import audit_full_mock
from .full_mock_raw_score import SCHEMA_VERSION

RENDERER_VERSION = "full_test_renderer_2026_11_17"


class RendererBridgeError(ValueError):
    pass


def renderer_key_map(content, *, skill, renderer_version):
    """Map each section's existing input keys to audit identities (keys only)."""
    if renderer_version != RENDERER_VERSION:
        raise RendererBridgeError("Unsupported renderer contract")
    leaves = audit_full_mock(content, skill=skill)
    result = {}
    targets = set()

    def add(mapping, source, target):
        if source in mapping or target in targets:
            raise RendererBridgeError("Ambiguous renderer identity")
        mapping[source] = target
        targets.add(target)

    for section in content["sections"]:
        sn = section["section_number"]
        mapping = result[sn] = {}
        questions = section["questions"]
        if skill == "reading":
            for gi, group in enumerate(questions["groups"]):
                kind = group["type"]
                # The current renderer ignores summary_text; matching information
                # synthesizes options from passage paragraphs rather than its
                # answer definitions. Neither is proven displayable by audit.
                if kind in {"summary_completion", "matching_information"}:
                    raise RendererBridgeError("Question type requires renderer review")
                if kind == "matching_headings":
                    for paragraph in group["items"]["paragraphs"]:
                        pid = paragraph["number"]
                        add(mapping, f"mh_{gi}_{pid}", f"s{sn}:heading{gi}:{pid}")
                else:
                    for qi, item in enumerate(group["items"]):
                        qid = item["question_number"]
                        suffix = qid if kind == "multiple_choice" else qi
                        add(mapping, f"q_{gi}_{suffix}", f"s{sn}:q{qid}")
        else:
            # Exact frontend toGroups order: completion, each matching block,
            # then MCQ. This is NOT the existing backend scorer's group order.
            groups = []
            if questions.get("completion"):
                groups.append(questions["completion"])
            for block in questions.get("matching", []):
                groups.append(block["stems"])
            if questions.get("multiple_choice"):
                groups.append(questions["multiple_choice"])
            for gi, items in enumerate(groups):
                for qi, item in enumerate(items):
                    add(mapping, f"q_{gi}_{qi}", f"s{sn}:q{item['question_number']}")
    if targets != {item.key for item in leaves}:
        raise RendererBridgeError("Renderer and audit leaves differ")
    return result


def translate_renderer_answers(content, sections, *, skill, renderer_version):
    """Translate an explicit section envelope, preserving answer strings exactly.

    Every section must appear once; missing input keys within a section remain
    unanswered. Reject unknown/duplicate sections, extra fields and foreign keys
    instead of guessing whether callers meant legacy scoring or localized IDs.
    """
    mapping = renderer_key_map(content, skill=skill, renderer_version=renderer_version)
    if not isinstance(sections, list):
        raise RendererBridgeError("Expected a section list")
    seen = set()
    translated = {}
    for row in sections:
        if not isinstance(row, dict) or set(row) != {"section_number", "answers"}:
            raise RendererBridgeError("Invalid renderer section envelope")
        sn = row["section_number"]
        if type(sn) is not int or sn not in mapping or sn in seen:
            raise RendererBridgeError("Unknown or duplicate renderer section")
        seen.add(sn)
        answers = row["answers"]
        if not isinstance(answers, dict):
            raise RendererBridgeError("Expected an answer object")
        for key, value in answers.items():
            if not isinstance(key, str) or key not in mapping[sn] or not isinstance(value, str):
                raise RendererBridgeError("Unknown renderer key or invalid answer")
            translated[mapping[sn][key]] = value
    if seen != set(mapping):
        raise RendererBridgeError("Missing renderer section")
    return {"schema_version": SCHEMA_VERSION, "answers": translated}
