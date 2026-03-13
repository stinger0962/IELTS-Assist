"""Configuration data for IELTS Grammar exercise generation.

30 grammar topics across 3 band levels, exercise type compositions,
IELTS context themes, and metadata generation — all used by grammar_generator.py.
"""

import random

# ─── 30 Grammar Topics (3 bands × 10) ─────────────────────────────────────

GRAMMAR_TOPICS = {
    "band_5_6": [
        {"id": 1, "name": "Subject-verb agreement", "key_pattern": "The number of X has/have...", "common_error": "using plural verb with collective/uncountable subjects"},
        {"id": 2, "name": "Tense consistency", "key_pattern": "Simple past vs present perfect", "common_error": "mixing tenses within a paragraph"},
        {"id": 3, "name": "Articles", "key_pattern": "a/an/the/zero article", "common_error": "omitting 'the' before specific nouns or adding it before generalizations"},
        {"id": 4, "name": "Countable vs uncountable nouns", "key_pattern": "much/many, fewer/less, amount/number", "common_error": "using 'less' with countable nouns"},
        {"id": 5, "name": "Basic prepositions", "key_pattern": "in/on/at for time and place", "common_error": "confusing in/on/at in time expressions"},
        {"id": 6, "name": "Pronoun reference", "key_pattern": "it/they/this referring back clearly", "common_error": "ambiguous pronoun reference"},
        {"id": 7, "name": "Comparatives and superlatives", "key_pattern": "more/most, -er/-est, irregular forms", "common_error": "double comparative (more bigger)"},
        {"id": 8, "name": "Basic conjunctions", "key_pattern": "and/but/so/because/although", "common_error": "run-on sentences or comma splices"},
        {"id": 9, "name": "Singular and plural nouns", "key_pattern": "irregular plurals, uncountable nouns", "common_error": "adding -s to uncountable nouns (informations, advices)"},
        {"id": 10, "name": "Basic word order", "key_pattern": "SVO, adverb placement, adjective order", "common_error": "misplacing adverbs of frequency"},
    ],
    "band_6_7": [
        {"id": 11, "name": "Conditionals", "key_pattern": "zero/first/second/third/mixed", "common_error": "using 'would' in the if-clause"},
        {"id": 12, "name": "Passive voice", "key_pattern": "be + past participle across tenses", "common_error": "incomplete passive (missing 'been' in present perfect passive)"},
        {"id": 13, "name": "Relative clauses", "key_pattern": "who/which/that, defining vs non-defining", "common_error": "using 'that' in non-defining clauses"},
        {"id": 14, "name": "Reported speech", "key_pattern": "tense backshift, say/tell/ask", "common_error": "failing to shift tense or pronoun"},
        {"id": 15, "name": "Gerunds vs infinitives", "key_pattern": "verb + -ing vs verb + to-infinitive", "common_error": "using infinitive after verbs that require gerund (enjoy to do)"},
        {"id": 16, "name": "Modal verbs for speculation", "key_pattern": "must/might/could/can't + have + pp", "common_error": "using 'can' instead of 'could' for past possibility"},
        {"id": 17, "name": "Complex prepositions", "key_pattern": "in terms of, with regard to, as a result of", "common_error": "incomplete or mixed prepositional phrases"},
        {"id": 18, "name": "Cause-effect connectors", "key_pattern": "consequently, as a result, thereby, hence", "common_error": "using connectors with wrong punctuation or grammar"},
        {"id": 19, "name": "Concession and contrast", "key_pattern": "although/despite/nevertheless/however", "common_error": "despite + clause instead of despite + noun/-ing"},
        {"id": 20, "name": "Parallel structure", "key_pattern": "matching grammatical forms in lists/comparisons", "common_error": "mixing forms: 'reading, writing, and to speak'"},
    ],
    "band_7_8": [
        {"id": 21, "name": "Inversion", "key_pattern": "Not only...but also, Seldom, Rarely, Never", "common_error": "forgetting auxiliary inversion after negative adverb"},
        {"id": 22, "name": "Cleft sentences", "key_pattern": "It is/was...that/who, What...is/was", "common_error": "incorrect pronoun or verb agreement in cleft"},
        {"id": 23, "name": "Participle clauses", "key_pattern": "Having studied, Being located, Faced with", "common_error": "dangling participle (wrong subject)"},
        {"id": 24, "name": "Nominalisation", "key_pattern": "verb/adj → noun: reduce → reduction, important → importance", "common_error": "awkward or incorrect noun form"},
        {"id": 25, "name": "Subjunctive mood", "key_pattern": "recommend that he study, it is essential that", "common_error": "using 'studies' instead of base form after subjunctive trigger"},
        {"id": 26, "name": "Reduced relative clauses", "key_pattern": "The study conducted by... / The data collected from...", "common_error": "using both relative pronoun and participle"},
        {"id": 27, "name": "Advanced articles", "key_pattern": "generalisation patterns, abstract nouns", "common_error": "adding 'the' before abstract generalizations"},
        {"id": 28, "name": "Hedging language", "key_pattern": "tend to, appear to, is likely to, it seems that", "common_error": "over-hedging or mixing hedging with certainty"},
        {"id": 29, "name": "Ellipsis and substitution", "key_pattern": "so/neither/nor, do so, one/ones", "common_error": "repeating full clause instead of using substitution"},
        {"id": 30, "name": "Emphasis structures", "key_pattern": "do/does/did for emphasis, It is X that...", "common_error": "using emphatic 'do' with wrong verb form"},
    ],
}

# ─── IELTS Context Themes ──────────────────────────────────────────────────
# Short IELTS-relevant scenarios for contextual exercises

CONTEXT_THEMES = [
    "university campus life and study habits",
    "urban planning and public transport",
    "environmental conservation efforts",
    "workplace culture and remote working",
    "healthcare access in rural areas",
    "tourism and its impact on local communities",
    "childhood education and learning styles",
    "technology adoption among older adults",
    "food production and sustainable agriculture",
    "climate change and coastal cities",
    "scientific research funding and ethics",
    "cultural heritage preservation",
    "immigration and multiculturalism",
    "renewable energy transition",
    "mental health awareness in schools",
    "water scarcity and management",
    "space exploration and technology",
    "social media influence on youth",
    "public library services and literacy",
    "wildlife conservation programs",
]

# ─── Exercise Type Compositions ────────────────────────────────────────────
# Each composition is a list of (type, count) tuples — 6-8 questions total
# v0.14.0: exact-match types only (error_correction, gap_fill, grammar_mcq)

EXERCISE_COMPOSITIONS = [
    [("error_correction", 3), ("gap_fill", 3), ("grammar_mcq", 2)],
    [("error_correction", 2), ("gap_fill", 4), ("grammar_mcq", 2)],
    [("error_correction", 3), ("grammar_mcq", 3), ("gap_fill", 2)],
    [("grammar_mcq", 3), ("gap_fill", 3), ("error_correction", 2)],
    [("error_correction", 4), ("gap_fill", 2), ("grammar_mcq", 2)],
    [("gap_fill", 4), ("grammar_mcq", 2), ("error_correction", 2)],
    [("grammar_mcq", 4), ("error_correction", 2), ("gap_fill", 2)],
    [("error_correction", 3), ("gap_fill", 2), ("grammar_mcq", 3)],
]


# ─── Metadata Generator ───────────────────────────────────────────────────

def generate_metadata(avoid_topics: list[str] | None = None) -> dict:
    """Generate grammar exercise metadata via pure Python randomization.

    Returns a dict with: grammar_topic (full object), band_level, context_theme,
    exercise_composition, total_questions.
    """
    avoid_set = set(t.lower() for t in (avoid_topics or []))

    # Collect all topics, filtering out recently used
    all_topics = []
    for band, topics in GRAMMAR_TOPICS.items():
        for t in topics:
            if t["name"].lower() not in avoid_set:
                all_topics.append((band, t))

    if not all_topics:
        all_topics = [(band, t) for band, topics in GRAMMAR_TOPICS.items() for t in topics]

    band_level, grammar_topic = random.choice(all_topics)

    context_theme = random.choice(CONTEXT_THEMES)
    composition = random.choice(EXERCISE_COMPOSITIONS)
    total_questions = sum(count for _, count in composition)

    return {
        "grammar_topic": grammar_topic,
        "band_level": band_level,
        "band_label": band_level.replace("band_", "Band ").replace("_", "-"),
        "context_theme": context_theme,
        "exercise_composition": composition,
        "total_questions": total_questions,
    }
