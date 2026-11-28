"""Whitelist-only experimental active-mock DTO. No legacy route integration.

Use private, reviewed full content on the server. The DTO omits answer
definitions, explanations, transcript, private metadata and feedback. Intentional
learning text (passages, prompts, options, audio) can inherently contain answers;
this is field separation, not semantic redaction or exam security certification.
"""
import re

from .full_mock_renderer_bridge import renderer_key_map

PREVIEW_VERSION = "full_mock_active_preview_v2"


class PreviewShapeError(ValueError):
    pass


def _question(key, kind, prompt, *, options=None, word_limit=None):
    result = {"key": key, "type": kind, "prompt": prompt}
    if options is not None:
        if kind not in {"true_false_not_given", "yes_no_not_given"} and any(
                re.fullmatch(r"[A-Z]", identifier) is None for identifier, _ in options):
            raise PreviewShapeError("Unsupported preview option identity")
        result["options"] = [{"id": identifier, "text": label} for identifier, label in options]
    if word_limit is not None:
        if type(word_limit) is not int or not 1 <= word_limit <= 100:
            raise PreviewShapeError("Invalid preview word limit")
        result["word_limit"] = word_limit
    return result


def _ordinary(item, kind, key):
    field = {
        "true_false_not_given": "statement", "yes_no_not_given": "statement",
        "multiple_choice": "question", "short_answer": "question",
        "sentence_completion": "text", "completion": "text",
    }[kind]
    options = None
    if kind == "multiple_choice":
        options = list(item["options"].items())
    elif kind in {"true_false_not_given", "yes_no_not_given"}:
        labels = ("TRUE", "FALSE", "NOT GIVEN") if kind == "true_false_not_given" else ("YES", "NO", "NOT GIVEN")
        options = [(label, label) for label in labels]
    return _question(key, kind, item[field], options=options,
                     word_limit=item.get("word_limit") if kind in {
                         "short_answer", "sentence_completion", "completion"} else None)


def active_mock_preview(content, *, skill, renderer_version):
    """Build a new detached DTO for the proven renderer subset, never passthrough.

    Callers must explicitly choose the pinned renderer contract; the returned
    flattened schema is not consumable by the existing full-test components.
    Keys are audit identities for a future versioned UI, not legacy input keys.
    """
    mapping = renderer_key_map(content, skill=skill, renderer_version=renderer_version)
    sections = []
    for source in content["sections"]:
        sn = source["section_number"]
        section = {"section_number": sn, "questions": []}
        questions = section["questions"]
        if skill == "reading":
            passage = source["passage"]
            section["passage"] = passage["content"] if isinstance(passage, dict) else passage
            for gi, group in enumerate(source["questions"]["groups"]):
                kind = group["type"]
                if kind == "matching_headings":
                    options = [(heading["id"], heading["text"]) for heading in group["items"]["headings"]]
                    for paragraph in group["items"]["paragraphs"]:
                        pid = paragraph["number"]
                        questions.append(_question(
                            mapping[sn][f"mh_{gi}_{pid}"], kind, paragraph["title"], options=options))
                else:
                    for qi, item in enumerate(group["items"]):
                        suffix = item["question_number"] if kind == "multiple_choice" else qi
                        questions.append(_ordinary(item, kind, mapping[sn][f"q_{gi}_{suffix}"]))
        else:
            audio = source["audio_url"]
            # Only same-origin controlled media paths; no arbitrary destination,
            # query credentials, percent-encoded aliases, traversal or data URLs.
            if not re.fullmatch(r"/audio/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:wav|mp3|ogg|m4a)", audio):
                raise PreviewShapeError("Preview requires a controlled relative audio path")
            section["audio_url"] = audio
            source_questions = source["questions"]
            gi = 0
            if source_questions.get("completion"):
                for qi, item in enumerate(source_questions["completion"]):
                    questions.append(_ordinary(item, "completion", mapping[sn][f"q_{gi}_{qi}"]))
                gi += 1
            for block in source_questions.get("matching", []):
                options = [(option.split(".", 1)[0], option.split(".", 1)[1].strip())
                           for option in block["options"]]
                for qi, stem in enumerate(block["stems"]):
                    questions.append(_question(mapping[sn][f"q_{gi}_{qi}"], "matching", stem["text"], options=options))
                gi += 1
            for qi, item in enumerate(source_questions.get("multiple_choice", [])):
                questions.append(_ordinary(item, "multiple_choice", mapping[sn][f"q_{gi}_{qi}"]))
        sections.append(section)
    return {"schema_version": PREVIEW_VERSION, "skill": skill, "total_questions": 40, "sections": sections}
