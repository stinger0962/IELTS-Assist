"""Configuration data for IELTS Grammar exercise generation.

60 grammar micro-skills across 3 band levels (20 each), 12 metadata dimensions,
exercise type compositions, and metadata generation — all used by grammar_generator.py.
"""

import random

# ─── 60 Grammar Micro-Skills (3 bands × 20) ──────────────────────────────

GRAMMAR_TOPICS = {
    "band_5_6": [
        {"id": 1, "name": "Subject-verb agreement", "key_pattern": "The number of X has/have...", "common_error": "using plural verb with collective/uncountable subjects", "gap_fill": True},
        {"id": 2, "name": "Tense consistency", "key_pattern": "Simple past vs present perfect", "common_error": "mixing tenses within a paragraph", "gap_fill": True},
        {"id": 3, "name": "Articles", "key_pattern": "a/an/the/zero article", "common_error": "omitting 'the' before specific nouns or adding it before generalizations", "gap_fill": False},
        {"id": 4, "name": "Countable vs uncountable nouns", "key_pattern": "much/many, fewer/less, amount/number", "common_error": "using 'less' with countable nouns", "gap_fill": False},
        {"id": 5, "name": "Basic prepositions", "key_pattern": "in/on/at for time and place", "common_error": "confusing in/on/at in time expressions", "gap_fill": False},
        {"id": 6, "name": "Pronoun reference", "key_pattern": "it/they/this referring back clearly", "common_error": "ambiguous pronoun reference", "gap_fill": False},
        {"id": 7, "name": "Comparatives and superlatives", "key_pattern": "more/most, -er/-est, irregular forms", "common_error": "double comparative (more bigger)", "gap_fill": True},
        {"id": 8, "name": "Basic conjunctions", "key_pattern": "and/but/so/because/although", "common_error": "run-on sentences or comma splices", "gap_fill": False},
        {"id": 9, "name": "Singular and plural nouns", "key_pattern": "irregular plurals, uncountable nouns", "common_error": "adding -s to uncountable nouns (informations, advices)", "gap_fill": True},
        {"id": 10, "name": "Basic word order", "key_pattern": "SVO, adverb placement, adjective order", "common_error": "misplacing adverbs of frequency", "gap_fill": False},
        {"id": 11, "name": "Modal verbs (basic)", "key_pattern": "can/could/should/must for ability, advice, obligation", "common_error": "using 'can' for past ability instead of 'could'", "gap_fill": True},
        {"id": 12, "name": "Simple tenses", "key_pattern": "present simple vs continuous, past simple vs continuous", "common_error": "using present continuous for permanent states", "gap_fill": True},
        {"id": 13, "name": "Question formation", "key_pattern": "do/does/did inversion, wh-questions, tag questions", "common_error": "missing auxiliary in questions (Where you go?)", "gap_fill": True},
        {"id": 14, "name": "Negative forms", "key_pattern": "don't/doesn't/didn't, no/not/never", "common_error": "double negatives (I don't have nothing)", "gap_fill": True},
        {"id": 15, "name": "Possessives", "key_pattern": "'s/s', of + noun, possessive pronouns (mine/yours)", "common_error": "confusing its/it's, whose/who's", "gap_fill": False},
        {"id": 16, "name": "Demonstratives", "key_pattern": "this/that/these/those for reference and distance", "common_error": "using 'this' for previously mentioned items instead of 'that'", "gap_fill": False},
        {"id": 17, "name": "Basic adverbs", "key_pattern": "adverbs of manner (-ly), degree (very/quite/rather)", "common_error": "using adjective instead of adverb (speak quick vs quickly)", "gap_fill": True},
        {"id": 18, "name": "Frequency adverbs", "key_pattern": "always/usually/often/sometimes/rarely/never + position", "common_error": "placing frequency adverb after the main verb instead of before", "gap_fill": False},
        {"id": 19, "name": "There is/are constructions", "key_pattern": "there is/are/was/were + noun phrase", "common_error": "using 'there is' with plural nouns", "gap_fill": True},
        {"id": 20, "name": "Basic quantifiers", "key_pattern": "some/any/much/many/a few/a little/each/every", "common_error": "using 'much' with countable nouns or 'many' with uncountable", "gap_fill": False},
    ],
    "band_6_7": [
        {"id": 21, "name": "Present perfect vs past simple", "key_pattern": "have/has + pp vs V2, time markers (yet/already/ago/in 2010)", "common_error": "using present perfect with specific past time (I have seen it yesterday)", "gap_fill": True},
        {"id": 22, "name": "Passive voice (simple)", "key_pattern": "be + past participle across tenses", "common_error": "incomplete passive (missing 'been' in present perfect passive)", "gap_fill": True},
        {"id": 23, "name": "Conditionals (1st and 2nd)", "key_pattern": "if + present → will; if + past → would", "common_error": "using 'would' in the if-clause", "gap_fill": True},
        {"id": 24, "name": "Relative clauses (defining)", "key_pattern": "who/which/that/where/when in defining clauses", "common_error": "using 'that' in non-defining clauses or omitting relative pronoun incorrectly", "gap_fill": False},
        {"id": 25, "name": "Gerunds vs infinitives", "key_pattern": "verb + -ing vs verb + to-infinitive", "common_error": "using infinitive after verbs that require gerund (enjoy to do)", "gap_fill": True},
        {"id": 26, "name": "Reported speech (basic)", "key_pattern": "tense backshift, say/tell/ask + that-clause", "common_error": "failing to shift tense or pronoun in indirect speech", "gap_fill": True},
        {"id": 27, "name": "Phrasal verbs", "key_pattern": "verb + particle combinations (carry out, look into, bring about)", "common_error": "wrong particle (carry on vs carry out) or separability errors", "gap_fill": True},
        {"id": 28, "name": "Collocations", "key_pattern": "make/do, strong/heavy, deeply/highly + adjective", "common_error": "wrong verb-noun collocation (make a decision vs do a decision)", "gap_fill": False},
        {"id": 29, "name": "Noun clauses", "key_pattern": "that/what/whether/how + clause as subject or object", "common_error": "using 'that' instead of 'what' (That he said was wrong → What he said)", "gap_fill": False},
        {"id": 30, "name": "Adverbial clauses", "key_pattern": "when/while/before/after/since/until + clause", "common_error": "using future tense in time clauses (when I will arrive → when I arrive)", "gap_fill": True},
        {"id": 31, "name": "Participle phrases", "key_pattern": "V-ing/V-ed phrases as modifiers: Walking to class, Surprised by the results", "common_error": "dangling modifier (Walking to class, the bell rang)", "gap_fill": True},
        {"id": 32, "name": "Causative structures", "key_pattern": "have/get something done, make/let someone do", "common_error": "wrong form after causative (have him to fix → have him fix)", "gap_fill": True},
        {"id": 33, "name": "Future forms", "key_pattern": "will/going to/present continuous for future, be about to", "common_error": "using 'will' for planned arrangements (I will meet him tomorrow at 3)", "gap_fill": True},
        {"id": 34, "name": "Hedging language", "key_pattern": "tend to, appear to, is likely to, it seems that", "common_error": "over-hedging or mixing hedging with certainty", "gap_fill": False},
        {"id": 35, "name": "Concession clauses", "key_pattern": "although/even though/despite/in spite of/while", "common_error": "despite + clause instead of despite + noun/-ing", "gap_fill": False},
        {"id": 36, "name": "Purpose clauses", "key_pattern": "to/in order to/so that/so as to + purpose", "common_error": "using 'for + verb-ing' when 'to + infinitive' is needed", "gap_fill": False},
        {"id": 37, "name": "Result clauses", "key_pattern": "so...that, such...that, consequently, as a result", "common_error": "confusing so/such (so big problem → such a big problem)", "gap_fill": True},
        {"id": 38, "name": "Contrast clauses", "key_pattern": "while/whereas/on the other hand/in contrast/however", "common_error": "using 'but' where 'however' or 'whereas' is more appropriate in academic writing", "gap_fill": False},
        {"id": 39, "name": "Addition and exemplification", "key_pattern": "moreover/furthermore/for instance/such as/namely", "common_error": "using 'for example' with comma splice or wrong punctuation", "gap_fill": False},
        {"id": 40, "name": "Substitution and ellipsis", "key_pattern": "so/neither/nor, do so, one/ones, omission of repeated elements", "common_error": "repeating full clause instead of using substitution", "gap_fill": False},
    ],
    "band_7_8": [
        {"id": 41, "name": "Inversion for emphasis", "key_pattern": "Not only...but also, Seldom, Rarely, Never + aux inversion", "common_error": "forgetting auxiliary inversion after negative adverb", "gap_fill": True},
        {"id": 42, "name": "Cleft sentences", "key_pattern": "It is/was...that/who, What...is/was", "common_error": "incorrect pronoun or verb agreement in cleft", "gap_fill": True},
        {"id": 43, "name": "Mixed conditionals", "key_pattern": "if + past perfect → would (present); if + past → would have (past)", "common_error": "using same tense pattern as 2nd/3rd conditional instead of mixing", "gap_fill": True},
        {"id": 44, "name": "Subjunctive mood", "key_pattern": "recommend that he study, it is essential that + base form", "common_error": "using 'studies' instead of base form after subjunctive trigger", "gap_fill": True},
        {"id": 45, "name": "Advanced passive (get-passive, have-causative)", "key_pattern": "get + pp (got injured), have + obj + pp (had it repaired)", "common_error": "confusing 'have something done' (causative) with 'have done something' (perfect)", "gap_fill": True},
        {"id": 46, "name": "Nominalisation", "key_pattern": "verb/adj → noun: reduce → reduction, important → importance", "common_error": "awkward or incorrect noun form in academic writing", "gap_fill": True},
        {"id": 47, "name": "Fronting and topicalization", "key_pattern": "Object/adverbial fronted: This issue, the committee addressed...", "common_error": "fronting without adjusting word order of remaining clause", "gap_fill": False},
        {"id": 48, "name": "Emphatic structures", "key_pattern": "do/does/did for emphasis, It is X that..., What X did was...", "common_error": "using emphatic 'do' with wrong verb form", "gap_fill": True},
        {"id": 49, "name": "Reduced relative clauses", "key_pattern": "The study conducted by... / The data collected from...", "common_error": "using both relative pronoun and participle", "gap_fill": True},
        {"id": 50, "name": "Parallel structure", "key_pattern": "matching grammatical forms in lists/comparisons", "common_error": "mixing forms: 'reading, writing, and to speak'", "gap_fill": True},
        {"id": 51, "name": "Complex noun phrases", "key_pattern": "determiner + pre-modifier + noun + post-modifier (the recently published government report on...)", "common_error": "over-stacking modifiers creating ambiguity", "gap_fill": False},
        {"id": 52, "name": "Apposition", "key_pattern": "noun phrase, explanatory phrase, ... (Dr Smith, a leading expert, argued...)", "common_error": "missing commas around non-restrictive appositive", "gap_fill": False},
        {"id": 53, "name": "Discourse markers (advanced)", "key_pattern": "nonetheless/notwithstanding/be that as it may/accordingly", "common_error": "using informal discourse markers in academic writing", "gap_fill": False},
        {"id": 54, "name": "Complex hedging", "key_pattern": "It could be argued that / There is some evidence to suggest / This may indicate", "common_error": "double hedging (It might possibly perhaps suggest)", "gap_fill": False},
        {"id": 55, "name": "Advanced cohesion", "key_pattern": "lexical chains, reference chains (the former/the latter/the aforementioned)", "common_error": "unclear reference with 'the former' when more than two items mentioned", "gap_fill": False},
        {"id": 56, "name": "Formal register shifts", "key_pattern": "commence vs start, sufficient vs enough, prior to vs before", "common_error": "mixing informal and formal register within academic paragraph", "gap_fill": False},
        {"id": 57, "name": "Abstract noun patterns", "key_pattern": "the + abstract noun + of (the importance of, the impact of, the extent to which)", "common_error": "omitting article before abstract noun in specific context", "gap_fill": True},
        {"id": 58, "name": "Advanced modality", "key_pattern": "be to / be bound to / be liable to / would appear to", "common_error": "using 'must' for academic certainty instead of 'would appear to'", "gap_fill": True},
        {"id": 59, "name": "Ellipsis in formal writing", "key_pattern": "omitting repeated elements: She studies French and (she studies) German", "common_error": "ellipsis creating grammatical ambiguity", "gap_fill": False},
        {"id": 60, "name": "Advanced reference chains", "key_pattern": "this/these + summary noun (this phenomenon, these findings, such measures)", "common_error": "using 'this' alone without a summary noun in academic writing", "gap_fill": False},
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

# ─── New Dimensions (6 additional) ────────────────────────────────────────

SENTENCE_COMPLEXITIES = ["simple", "compound", "complex", "compound-complex"]

ERROR_TYPES = ["omission", "substitution", "word_order", "redundancy", "wrong_form"]

REGISTERS = [
    "academic_essay",
    "news_report",
    "lecture_transcript",
    "formal_letter",
    "research_abstract",
]

PARAPHRASE_DISTANCES = ["near", "medium", "far"]

COGNITIVE_DIFFICULTIES = ["recognition", "production", "transformation", "evaluation"]

SKILL_INTEGRATIONS = ["reading_grammar", "listening_grammar", "writing_grammar"]

# ─── Exercise Type Compositions ────────────────────────────────────────────
# Each composition is a list of (type, count) tuples — 6-8 questions total
# v0.16.0: 6 types (error_correction, gap_fill, grammar_mcq,
#           sentence_transformation, sentence_combination, context_completion)

EXERCISE_COMPOSITIONS = [
    # Classic compositions (original 3 types)
    [("error_correction", 3), ("gap_fill", 3), ("grammar_mcq", 2)],
    [("error_correction", 2), ("gap_fill", 4), ("grammar_mcq", 2)],
    [("grammar_mcq", 3), ("gap_fill", 3), ("error_correction", 2)],
    [("grammar_mcq", 4), ("error_correction", 2), ("gap_fill", 2)],
    # Mixed compositions (old + new types)
    [("error_correction", 2), ("gap_fill", 2), ("sentence_transformation", 2), ("grammar_mcq", 2)],
    [("gap_fill", 2), ("sentence_transformation", 2), ("sentence_combination", 2), ("grammar_mcq", 2)],
    [("error_correction", 2), ("sentence_combination", 2), ("context_completion", 2), ("grammar_mcq", 2)],
    [("sentence_transformation", 2), ("gap_fill", 2), ("error_correction", 2), ("grammar_mcq", 2)],
    [("error_correction", 2), ("gap_fill", 2), ("context_completion", 2), ("sentence_transformation", 2)],
    [("sentence_combination", 2), ("error_correction", 2), ("grammar_mcq", 2), ("gap_fill", 2)],
    # New-type-heavy compositions
    [("sentence_transformation", 3), ("sentence_combination", 2), ("context_completion", 2), ("grammar_mcq", 1)],
    [("context_completion", 3), ("sentence_transformation", 2), ("error_correction", 2), ("gap_fill", 1)],
]

# Compositions for topics where gap_fill is unsuitable (articles, prepositions, etc.)
NO_GAP_FILL_COMPOSITIONS = [
    [("error_correction", 4), ("grammar_mcq", 4)],
    [("error_correction", 3), ("grammar_mcq", 3), ("sentence_transformation", 2)],
    [("grammar_mcq", 3), ("sentence_transformation", 2), ("error_correction", 3)],
    [("error_correction", 2), ("sentence_combination", 2), ("grammar_mcq", 2), ("context_completion", 2)],
    [("sentence_transformation", 2), ("context_completion", 2), ("grammar_mcq", 2), ("error_correction", 2)],
    [("grammar_mcq", 3), ("error_correction", 3), ("sentence_combination", 2)],
]


# ─── Metadata Generator ───────────────────────────────────────────────────

def generate_metadata(avoid_topics: list[str] | None = None) -> dict:
    """Generate grammar exercise metadata via pure Python randomization.

    Returns a dict with: grammar_topic (full object), band_level, 12 dimensions,
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

    # Pick composition based on whether the topic supports gap_fill
    if grammar_topic.get("gap_fill", True):
        composition = random.choice(EXERCISE_COMPOSITIONS)
    else:
        composition = random.choice(NO_GAP_FILL_COMPOSITIONS)

    total_questions = sum(count for _, count in composition)

    return {
        "grammar_topic": grammar_topic,
        "band_level": band_level,
        "band_label": band_level.replace("band_", "Band ").replace("_", "-"),
        "context_theme": context_theme,
        "exercise_composition": composition,
        "total_questions": total_questions,
        # New dimensions (v0.15.0)
        "sentence_complexity": random.choice(SENTENCE_COMPLEXITIES),
        "error_type": random.choice(ERROR_TYPES),
        "register": random.choice(REGISTERS),
        "paraphrase_distance": random.choice(PARAPHRASE_DISTANCES),
        "cognitive_difficulty": random.choice(COGNITIVE_DIFFICULTIES),
        "skill_integration": random.choice(SKILL_INTEGRATIONS),
    }
