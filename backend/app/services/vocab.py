"""Vocabulary lookup: definition, IPA, Chinese and self-hosted pronunciation.

Replaces api.dictionaryapi.dev — a free, unauthenticated service with no SLA that
was called directly from the browser, and whose audio URLs were persisted into
topics rows. An outage there would have retroactively broken saved vocabulary,
not just new lookups.
"""

import json
import logging

from app.services.ai.llm import chat_json

logger = logging.getLogger(__name__)

LOOKUP_PROMPT = (
    "You are a lexicographer helping Chinese-speaking IELTS students.\n"
    "For the given English word, return JSON with these keys:\n"
    '  "definition_en": a clear one-sentence definition in simple English\n'
    '  "definition_zh": the same meaning in natural Simplified Chinese\n'
    '  "example":       one natural example sentence using the word\n'
    '  "phonetic":      British IPA in slashes, e.g. /ˈæmplɪfaɪ/\n'
    "If a sentence of context is supplied, define the sense used there.\n"
    "No commentary, no pinyin."
)


def normalise(word: str) -> str:
    """Cache key: words are looked up case-insensitively."""
    return word.strip().lower()


def parse_lookup(raw: str) -> dict:
    """Validate the model's JSON. A definition is mandatory; the rest are optional."""
    data = json.loads(raw)
    definition = (data.get("definition_en") or "").strip()
    if not definition:
        raise ValueError("model returned no definition_en")
    return {
        "definition_en": definition,
        "definition_zh": (data.get("definition_zh") or "").strip() or None,
        "example": (data.get("example") or "").strip() or None,
        "phonetic": (data.get("phonetic") or "").strip() or None,
    }


def generate_entry(word: str, context: str | None = None) -> dict:
    """One model call for definition + Chinese + example + IPA."""
    user = f"Word: {word}"
    if context:
        user += f"\nSentence it appeared in: {context}"
    raw = chat_json(
        tier="utility",
        messages=[
            {"role": "system", "content": LOOKUP_PROMPT},
            {"role": "user", "content": user},
        ],
        max_output_tokens=400,
        reasoning_effort="low",
    )
    return parse_lookup(raw)


def synthesize_pronunciation(word: str) -> str | None:
    """British-voice MP3 for the word. Audio is optional — never fail the lookup."""
    try:
        from app.services.tts import synthesize

        return synthesize(word, voice_key="british_female")
    except Exception as e:
        logger.warning("pronunciation synthesis failed for %r: %s", word, e)
        return None
