"""IELTS Writing Task 2 — Realism-upgraded grading pipeline (v2.0).

Layer A+B: Holistic scoring with soft penalties (1 grader-tier call, reasoning_effort=medium)
  - Full IELTS band descriptors (bands 4–9) for all 4 criteria
  - Soft penalty system: -0.5 / -1.0 / -1.5 (max -2.0 cumulative per criterion)
  - Idea depth & development quality baked into TR evaluation
  - Essay-type-specific task completion (soft pressure, not hard caps)
  - LR: precision > appropriateness > range
  - GRA: complexity × accuracy interaction
  - Anti-template detection
  - Dominant weakness flagging in coaching
  - Must quote evidence from the essay for each criterion

Layer C: Learner annotations (1 grader-tier call, reasoning_effort=low)
  - 6–8 annotations, ≥70% must be band-affecting
  - Added idea_development category
  - Fallback: if this call fails, scoring result still returned

Hard caps ONLY for: <150 words, completely off-topic.
"""

import json
import logging

from app.services.ai.bands import clamp_band
from app.services.ai.llm import chat_json, resolve_model

logger = logging.getLogger(__name__)

# ── IELTS Band Descriptors (4–9) ─────────────────────────────────────────────

BAND_DESCRIPTORS = """
## IELTS Writing Task 2 — Official Band Descriptors (Bands 4–9)

### Task Response (TR)
Band 9: Fully addresses all parts of the task. Presents a fully developed position with relevant, extended, and well-supported ideas.
Band 8: Sufficiently addresses all parts of the task. Presents a well-developed response with relevant, extended, and supported ideas.
Band 7: Addresses all parts of the task. Presents a clear position throughout. Main ideas are extended and supported, but there may be a tendency to over-generalise or lack focus.
Band 6: Addresses all parts of the task, though some parts may be more fully covered than others. Presents a relevant position, though conclusions may be unclear or repetitive. Main ideas are relevant but some may be inadequately developed or unclear.
Band 5: Addresses the task only partially. The format may be inappropriate in places. Expresses a position but development is not always clear. Some main ideas are put forward but limited. There may be irrelevant detail.
Band 4: Responds to the task only in a minimal way or the answer is tangential. The format may be inappropriate. Presents a position but this is unclear. Main ideas are difficult to identify and may be repetitive, irrelevant, or not sufficiently supported.

### Coherence and Cohesion (CC)
Band 9: Uses cohesion in such a way that it attracts no attention. Skilfully manages paragraphing.
Band 8: Sequences information and ideas logically. Manages all aspects of cohesion well. Uses paragraphing sufficiently and appropriately.
Band 7: Logically organises information and ideas; clear progression throughout. Uses a range of cohesive devices appropriately although there may be some under/over-use. Presents a clear central topic within each paragraph.
Band 6: Arranges information and ideas coherently; clear overall progression. Uses cohesive devices effectively but cohesion within and/or between sentences may be faulty or mechanical. May not always use referencing clearly or appropriately. Uses paragraphing but not always logically.
Band 5: Presents information with some organisation but may lack overall progression. Makes inadequate, inaccurate, or over-use of cohesive devices. May be repetitive. Paragraphing may be inadequate or missing.
Band 4: Presents information and ideas but these are not arranged coherently and there is no clear progression. Uses some basic cohesive devices but these may be inaccurate or repetitive. Paragraphing may be absent or confusing.

### Lexical Resource (LR)
Band 9: Uses a wide range of vocabulary with very natural and sophisticated control of lexical features; rare minor errors occur only as 'slips'.
Band 8: Uses a wide range of vocabulary fluently and flexibly to convey precise meanings. Skilfully uses uncommon lexical items; occasional inaccuracies in word choice and collocation. Produces rare errors in spelling and/or word formation.
Band 7: Uses a sufficient range of vocabulary to allow some flexibility and precision. Uses less common lexical items with some awareness of style and collocation. May produce occasional errors in word choice, spelling, and/or word formation.
Band 6: Uses an adequate range of vocabulary for the task. Attempts to use less common vocabulary but with some inaccuracy. Makes some errors in spelling and/or word formation but they do not impede communication.
Band 5: Uses a limited range of vocabulary, but this is minimally adequate for the task. May make noticeable errors in spelling and/or word formation that may cause some difficulty for the reader.
Band 4: Uses only basic vocabulary which may be used repetitively or which may be inappropriate for the task. Has limited control of word formation and/or spelling; errors may cause strain for the reader.

### Grammatical Range and Accuracy (GRA)
Band 9: Uses a wide range of structures with full flexibility and accuracy; rare minor errors occur only as 'slips'.
Band 8: Uses a wide range of structures. The majority of sentences are error-free. Makes only very occasional errors or inappropriacies.
Band 7: Uses a variety of complex structures. Produces frequent error-free sentences. Has good control of grammar and punctuation but may make a few errors.
Band 6: Uses a mix of simple and complex sentence forms. Makes some errors in grammar and punctuation but they rarely reduce communication.
Band 5: Uses only a limited range of structures. Attempts complex sentences but these tend to be less accurate than simple sentences. May make frequent grammatical errors; punctuation may be faulty.
Band 4: Uses only a very limited range of structures with only rare use of subordinate clauses. Some structures are accurate but errors predominate, and punctuation is often faulty.
"""

# ── Essay-type-specific task completion (soft penalties, not hard caps) ───────

TASK_COMPLETION_BY_TYPE = {
    "opinion": """
Task completion evaluation for OPINION essay ("To what extent do you agree or disagree?"):
- Does the writer maintain a clear position THROUGHOUT the essay (not just in conclusion)?
- Are arguments supported with specific evidence, not vague generalizations?
- Does the writer address the full extent (completely agree, partially, disagree)?
- If partially agreeing, are BOTH sides given fair treatment?

Soft penalties (apply as adjustments, NOT hard caps):
- Position only appears in conclusion → apply -1.0 penalty to TR
- No clear position discernible → apply -1.5 penalty to TR
- Position stated but arguments are generic/undeveloped → apply -0.5 penalty to TR

If the prompt could reasonably be interpreted as more than one essay type, evaluate task completion using the most favorable interpretation for the student.""",

    "discussion": """
Task completion evaluation for DISCUSSION essay ("Discuss both views and give your own opinion."):
- Are BOTH views genuinely discussed (not just mentioned then dismissed)?
- Does the writer give their OWN opinion (not just summarize others')?
- Is each view supported with reasons/examples?

Soft penalties (apply as adjustments, NOT hard caps):
- Own opinion missing or only appears as afterthought → apply -1.0 penalty to TR
- Only one view genuinely discussed → apply -1.5 penalty to TR
- Both views mentioned but neither developed with specifics → apply -0.5 penalty to TR

If the prompt could reasonably be interpreted as more than one essay type, evaluate task completion using the most favorable interpretation for the student.""",

    "problem_solution": """
Task completion evaluation for PROBLEM-SOLUTION essay:
- Are REAL, specific problems identified (not just restating the topic)?
- Are PRACTICAL, specific solutions proposed (not just "the government should do something")?
- Are problems and solutions balanced (not all problems, one-line solutions)?

Soft penalties (apply as adjustments, NOT hard caps):
- Solutions are vague or generic → apply -1.0 penalty to TR
- Either problems or solutions section is missing entirely → apply -1.5 penalty to TR
- Problems identified but solutions are surface-level → apply -0.5 penalty to TR

If the prompt could reasonably be interpreted as more than one essay type, evaluate task completion using the most favorable interpretation for the student.""",

    "advantages_disadvantages": """
Task completion evaluation for ADVANTAGES-DISADVANTAGES essay:
- Are BOTH advantages and disadvantages discussed with specific support?
- If asked "Do the advantages outweigh the disadvantages?", is a clear judgment given?
- Are points developed beyond listing (explanation + example)?

Soft penalties (apply as adjustments, NOT hard caps):
- Judgment missing when the prompt explicitly asks for one → apply -1.0 penalty to TR
- Only one side covered substantially → apply -1.5 penalty to TR
- Both sides listed but not developed → apply -0.5 penalty to TR

If the prompt could reasonably be interpreted as more than one essay type, evaluate task completion using the most favorable interpretation for the student.""",

    "two_part": """
Task completion evaluation for TWO-PART QUESTION essay:
- Are BOTH questions addressed substantially (not one fully, one briefly)?
- Is each question given roughly equal development?

Soft penalties (apply as adjustments, NOT hard caps):
- One question only superficially addressed → apply -1.0 penalty to TR
- One question completely ignored → apply -1.5 penalty to TR
- Both addressed but one significantly weaker → apply -0.5 penalty to TR

If the prompt could reasonably be interpreted as more than one essay type, evaluate task completion using the most favorable interpretation for the student.""",
}

# ── Holistic scoring calibration ─────────────────────────────────────────────

SCORING_CALIBRATION = """
## Scoring Calibration — Think Like an Examiner

You are a strict but fair IELTS examiner. Score holistically, not mechanically.
Cumulative penalties on any single criterion should NOT exceed -2.0 total.

### Soft Penalty System
Use these penalty weights instead of hard caps. Apply them as adjustments to the band you would otherwise give:
- Minor issue → -0.5
- Moderate issue → -1.0
- Severe issue → -1.5

### TASK RESPONSE — Idea Depth & Development

Evaluate the DEPTH of ideas, not just their presence:
- If ALL ideas are generic/template-level with no specific mechanisms, scenarios, or causal reasoning → TR cannot exceed 6.0. This is a hard ceiling for shallow writing.
- If ideas are relevant but lack causal explanation or concrete examples → TR cannot exceed 6.5.
- Only award TR 7+ if ideas demonstrate genuine thought: specific examples, clear cause-effect, or insightful analysis.

Development quality check — for each main idea the student presents, look for at least ONE of:
- An explanation of WHY or HOW
- A specific example (not "for example, many people...")
- A consequence or result

If fewer than half the main ideas include any of the above → apply -1.0 penalty to TR.
If most ideas are bare assertions with no development → apply -1.5 penalty to TR.

### Anti-Template Detection
- Memorized introductions ("In today's modern world...", "This essay will discuss both sides...") → apply -0.5 penalty to TR
- Template thesis statements that could apply to any topic → apply -0.5 penalty to TR
- Repetitive paragraph structure (identical pattern in every body paragraph: topic sentence → example → conclusion) → apply -0.5 penalty to TR
- Do NOT penalize formulaic language if the IDEAS underneath are specific and well-developed.

### COHERENCE & COHESION — Realism
- Only penalize mechanical connectors ("Furthermore", "Moreover", "In addition") if they are BOTH repetitive AND reduce clarity or feel forced.
- If connectors are mechanical but the essay still flows clearly → CC max 7.0 (not lower).
- REWARD implicit cohesion: pronoun reference, logical flow without signpost words, natural paragraph transitions → apply +0.5 bonus to CC.

### LEXICAL RESOURCE — Precision Priority
Evaluate in this order (most important first):
1. PRECISION — Does the vocabulary convey exactly what the writer means?
2. APPROPRIATENESS — Is it suitable for the register and topic?
3. RANGE — How varied is the vocabulary?

- Wrong collocations → apply -0.5 per instance (max -1.0 total for collocations)
- Forced/shoehorned advanced vocabulary that doesn't fit naturally → LR max 6.5
- Accurate, natural use of topic-specific vocabulary → apply +0.5 bonus to LR
- Simple but precise vocabulary is better than ambitious but inaccurate vocabulary.

### GRAMMATICAL RANGE & ACCURACY — Complexity × Accuracy
Evaluate the interaction between complexity and accuracy:
- Complex structures attempted but frequently wrong → GRA max 6.0
- Simple structures only, but mostly accurate → GRA max 6.5
- Band 7+ requires BOTH variety of structures AND reasonable accuracy
- Do NOT reward complexity that consistently produces errors — accuracy matters more.

### WORD COUNT PENALTIES (hard-enforced)
These are the ONLY hard caps in the system:
- 200–249 words → apply -0.5 penalty to TR
- 150–199 words → apply -1.5 penalty to TR, cap CC/LR/GRA at 6.0
- Under 150 words → cap TR at 4.0, cap CC/LR/GRA at 5.0. The essay is fundamentally incomplete and cannot be scored normally regardless of quality.

### OFF-TOPIC (hard-enforced)
- Completely off-topic → cap TR at 4.0
- Only tangentially related → cap TR at 5.0

### General Calibration
- Do NOT inflate scores for fluent but underdeveloped writing. Length and fluency ≠ depth.
- A truly Band 8+ essay is rare — it requires sophisticated, precise, well-developed writing throughout.
- Essay reads smoothly but says nothing specific → max 6.5 overall.
- Complex grammar attempted but frequently incorrect → GRA 5.5–6.0, not higher.

### Dominant Weakness
- If any criterion scores ≤5.0, note this explicitly in coaching_feedback as a "dominant weakness limiting overall band" and suggest it as the #1 priority for improvement.
"""

# ── Layer A+B: Scoring prompt ────────────────────────────────────────────────

SCORING_SYSTEM_PROMPT = """You are a senior IELTS Writing examiner with 15+ years of experience.
Score this Task 2 essay using the official IELTS band descriptors below.
You must quote direct evidence from the essay for every score you assign.
Think holistically like a real examiner — apply judgment, not mechanical rules.

{band_descriptors}

{task_completion_instructions}

{scoring_calibration}

## Scoring Pipeline (follow this order)

1. Read the essay carefully in relation to the ORIGINAL PROMPT.
2. BASE SCORING: For each of the 4 criteria, determine a starting band (whole or .5 increments, range 4.0–9.0) based on the band descriptors.
3. TASK COMPLETION: Apply essay-type-specific soft penalties to TR.
4. IDEA DEPTH & DEVELOPMENT: Evaluate depth and development quality; adjust TR accordingly.
5. LANGUAGE REFINEMENT: Apply LR precision-priority and GRA complexity×accuracy rules.
6. SOFT PENALTIES: Apply any remaining penalties (anti-template, cohesion, etc.). Remember: max -2.0 cumulative per criterion.
7. DOMINANT WEAKNESS: If any criterion ≤5.0, flag it in coaching feedback.
8. FINAL: Calculate overall_band as the arithmetic mean of all 4 criteria, rounded to nearest 0.5.
9. Write coaching: 1–2 sentence overview, 2–3 strengths, 2–3 improvements. If dominant weakness exists, make it improvement #1.

## Output Format (strict JSON, no markdown)

{{
  "examiner_result": {{
    "task_response": {{
      "band": <number>,
      "evidence": "<string with specific quotes>",
      "task_completion": {{
        "answered_all_parts": <bool>,
        "clear_position": <bool>,
        "sufficient_support": <bool>,
        "paragraphing_effective": <bool>
      }}
    }},
    "coherence_cohesion": {{
      "band": <number>,
      "evidence": "<string with specific quotes>"
    }},
    "lexical_resource": {{
      "band": <number>,
      "evidence": "<string with specific quotes>"
    }},
    "grammatical_range_accuracy": {{
      "band": <number>,
      "evidence": "<string with specific quotes>"
    }},
    "overall_band": <number>
  }},
  "coaching_feedback": {{
    "summary": "<1-2 sentence overview>",
    "strengths": ["<strength 1>", "<strength 2>"],
    "improvements": ["<improvement 1>", "<improvement 2>"]
  }}
}}
"""

# ── Layer C: Annotation prompt ───────────────────────────────────────────────

ANNOTATION_SYSTEM_PROMPT = """You are an IELTS Writing feedback specialist. Your task is to annotate specific errors and weaknesses in the essay below.

## Rules
1. Return EXACTLY 6–8 annotations. At least 70% (5+) MUST be band-affecting ("major" severity). Minimize cosmetic corrections.
2. Each annotation must include character offsets (start_char, end_char) measured from the START of the essay text.
3. Categories: grammar, vocabulary, spelling, punctuation, coherence, style, idea_development
4. Severity: "major" (affects band score) or "minor" (worth noting but doesn't change band)
5. Suggestions must be specific and actionable — not "improve this" but "use 'exacerbate' instead of 'make worse'"
6. Do NOT annotate every small error. Focus on patterns that hurt the band score most.
7. Priority: idea_development (undeveloped points) > grammar errors > vocabulary imprecision > coherence issues > spelling > punctuation > style
8. For idea_development annotations: select a sentence or passage that represents an undeveloped idea, and explain what development is missing (e.g., "This point asserts X but gives no explanation of why — add a cause-effect chain or specific example to push TR toward Band 7").

## Scoring context (use this to focus annotations on band-limiting issues)
Task Response: {tr_band} | Coherence: {cc_band} | Lexical: {lr_band} | Grammar: {gra_band}

## Output Format (strict JSON object, no markdown)

Return a single JSON object whose "annotations" key holds the array:

{{
  "annotations": [
    {{
      "start_char": <int>,
      "end_char": <int>,
      "original_text": "<exact substring from essay>",
      "category": "<grammar|vocabulary|spelling|punctuation|coherence|style|idea_development>",
      "suggestion": "<specific fix or alternative>",
      "severity": "<major|minor>"
    }}
  ]
}}

IMPORTANT: start_char and end_char are 0-based character indices into the essay text.
Verify that essay[start_char:end_char] == original_text for each annotation.
"""


class WritingGrader:
    """Realism-upgraded IELTS Writing Task 2 grader using the configured grader tier (v2.0)."""

    GRADER_VERSION = "2.0"

    def __init__(self):
        # Recorded into the result payload and surfaced in the UI.
        self.model = resolve_model("grader")

    def grade(self, essay: str, prompt_data: dict) -> dict:
        """Full grading pipeline. Returns examiner result + coaching + annotations."""
        # Layer A+B: holistic scoring with soft penalties
        scoring = self._score_essay(essay, prompt_data)

        # Layer C: learner annotations (fallback-safe)
        annotations = []
        try:
            annotations = self._annotate_errors(essay, prompt_data, scoring)
        except Exception as e:
            logger.warning(f"Annotation layer failed (scoring still valid): {e}")

        result = {**scoring, "annotations": annotations}
        result["grader_version"] = self.GRADER_VERSION
        result["model"] = self.model
        return result

    def _score_essay(self, essay: str, prompt_data: dict) -> dict:
        """Layer A+B: Holistic scoring with soft penalties and idea depth."""
        essay_type = prompt_data.get("essay_type", "opinion")
        task_instructions = TASK_COMPLETION_BY_TYPE.get(
            essay_type, TASK_COMPLETION_BY_TYPE["opinion"]
        )

        system_prompt = SCORING_SYSTEM_PROMPT.format(
            band_descriptors=BAND_DESCRIPTORS,
            task_completion_instructions=task_instructions,
            scoring_calibration=SCORING_CALIBRATION,
        )

        word_count = len(essay.split())
        user_prompt = (
            f"## IELTS Writing Task 2 Prompt\n"
            f"Essay type: {essay_type}\n"
            f"Statement: {prompt_data.get('statement', '')}\n"
            f"Instruction: {prompt_data.get('instruction', '')}\n\n"
            f"## Student's Essay ({word_count} words)\n\n"
            f"{essay}"
        )

        raw = chat_json(
            tier="grader",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=2000,
            temperature=0,
            reasoning_effort="medium",
        )
        scoring = json.loads(raw)

        er = scoring.get("examiner_result", {})

        # ── Keep every band inside the range the descriptors define ──
        # Runs BEFORE the caps and the mean, so an off-scale value cannot drag
        # the overall down. Production was seen returning 2.5 and 3.0, which no
        # part of the supplied rubric can justify.
        for criterion in ("task_response", "coherence_cohesion",
                          "lexical_resource", "grammatical_range_accuracy"):
            crit = er.get(criterion)
            if isinstance(crit, dict):
                crit["band"] = clamp_band(crit.get("band"), criterion=criterion,
                                          context=f"({word_count} words)")

        # ── Programmatic word count safety net ──
        # Hard caps ONLY for severe under-length (the prompt instructs GPT to
        # handle 200-249 via soft penalty, so no code override for that range)
        if word_count < 150:
            hard_caps = {
                "task_response": 4.0,
                "coherence_cohesion": 5.0,
                "lexical_resource": 5.0,
                "grammatical_range_accuracy": 5.0,
            }
            for criterion, cap in hard_caps.items():
                crit = er.get(criterion, {})
                if crit.get("band", 0) > cap:
                    crit["band"] = cap
        elif word_count < 200:
            # Ensure TR got at least -1.5 penalty (soft, but verify)
            soft_caps = {
                "coherence_cohesion": 6.0,
                "lexical_resource": 6.0,
                "grammatical_range_accuracy": 6.0,
            }
            for criterion, cap in soft_caps.items():
                crit = er.get(criterion, {})
                if crit.get("band", 0) > cap:
                    crit["band"] = cap

        # ── Recalculate overall as arithmetic mean ──
        bands = [
            er.get("task_response", {}).get("band", 0),
            er.get("coherence_cohesion", {}).get("band", 0),
            er.get("lexical_resource", {}).get("band", 0),
            er.get("grammatical_range_accuracy", {}).get("band", 0),
        ]
        computed = round(sum(bands) / 4 * 2) / 2  # round to nearest 0.5
        er["overall_band"] = computed

        return scoring

    @staticmethod
    def _coerce_annotations(parsed) -> list:
        """Normalise whatever shape the model returned into a list of annotations.

        json_object mode forbids a bare top-level array, so the prompt asks for
        {"annotations": [...]}. Models still occasionally emit a bare list, or a
        single annotation object — both are accepted rather than silently dropped.
        """
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ("annotations", "items", "data"):
                value = parsed.get(key)
                if isinstance(value, list):
                    return value
            # A lone annotation object, returned without the wrapper.
            if "original_text" in parsed:
                return [parsed]
        return []

    def _annotate_errors(self, essay: str, prompt_data: dict, scoring: dict) -> list:
        """Layer C: 6–8 annotations (≥70% band-affecting), including idea_development."""
        er = scoring.get("examiner_result", {})

        system_prompt = ANNOTATION_SYSTEM_PROMPT.format(
            tr_band=er.get("task_response", {}).get("band", "?"),
            cc_band=er.get("coherence_cohesion", {}).get("band", "?"),
            lr_band=er.get("lexical_resource", {}).get("band", "?"),
            gra_band=er.get("grammatical_range_accuracy", {}).get("band", "?"),
        )

        user_prompt = (
            f"## Original Prompt\n"
            f"Statement: {prompt_data.get('statement', '')}\n"
            f"Instruction: {prompt_data.get('instruction', '')}\n\n"
            f"## Essay to annotate\n\n"
            f"{essay}"
        )

        raw = chat_json(
            tier="grader",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=1500,
            temperature=0.2,
            reasoning_effort="low",
        )
        annotations = self._coerce_annotations(json.loads(raw))

        # Validate and fix character offsets where possible
        validated = []
        for ann in annotations:
            original = ann.get("original_text", "")
            start = ann.get("start_char")
            end = ann.get("end_char")

            # If offsets don't match, try to find the text in the essay
            if start is not None and end is not None:
                actual = essay[start:end]
                if actual != original and original:
                    idx = essay.find(original)
                    if idx >= 0:
                        ann["start_char"] = idx
                        ann["end_char"] = idx + len(original)
                    else:
                        continue
            elif original:
                idx = essay.find(original)
                if idx >= 0:
                    ann["start_char"] = idx
                    ann["end_char"] = idx + len(original)
                else:
                    continue

            validated.append(ann)

        return validated[:8]  # Cap at 8
