"""IELTS Writing Task 2 — Evidence-based 3-layer grading pipeline.

Layer A+B: Rubric analysis + score decision (1 GPT-4o call, temperature=0)
  - Full IELTS band descriptors (bands 5–9) for all 4 criteria
  - Essay-type-specific task completion checks
  - Harshness calibration: no inflation for fluent-but-shallow writing
  - Must quote evidence from the essay for each criterion

Layer C: Learner annotations (1 GPT-4o call, temperature=0.2)
  - 6–8 high-value annotations with character offsets
  - Prioritizes band-affecting issues over cosmetic ones
  - Fallback: if this call fails, scoring result still returned
"""

import json
import logging
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)

# ── IELTS Band Descriptors (5–9) embedded in scoring prompt ──────────────────

BAND_DESCRIPTORS = """
## IELTS Writing Task 2 — Official Band Descriptors (Bands 5–9)

### Task Response (TR)
Band 9: Fully addresses all parts of the task. Presents a fully developed position with relevant, extended, and well-supported ideas.
Band 8: Sufficiently addresses all parts of the task. Presents a well-developed response with relevant, extended, and supported ideas.
Band 7: Addresses all parts of the task. Presents a clear position throughout. Main ideas are extended and supported, but there may be a tendency to over-generalise or lack focus.
Band 6: Addresses all parts of the task, though some parts may be more fully covered than others. Presents a relevant position, though conclusions may be unclear or repetitive. Main ideas are relevant but some may be inadequately developed or unclear.
Band 5: Addresses the task only partially. The format may be inappropriate in places. Expresses a position but development is not always clear. Some main ideas are put forward but limited. There may be irrelevant detail.

### Coherence and Cohesion (CC)
Band 9: Uses cohesion in such a way that it attracts no attention. Skilfully manages paragraphing.
Band 8: Sequences information and ideas logically. Manages all aspects of cohesion well. Uses paragraphing sufficiently and appropriately.
Band 7: Logically organises information and ideas; clear progression throughout. Uses a range of cohesive devices appropriately although there may be some under/over-use. Presents a clear central topic within each paragraph.
Band 6: Arranges information and ideas coherently; clear overall progression. Uses cohesive devices effectively but cohesion within and/or between sentences may be faulty or mechanical. May not always use referencing clearly or appropriately. Uses paragraphing but not always logically.
Band 5: Presents information with some organisation but may lack overall progression. Makes inadequate, inaccurate, or over-use of cohesive devices. May be repetitive. Paragraphing may be inadequate or missing.

### Lexical Resource (LR)
Band 9: Uses a wide range of vocabulary with very natural and sophisticated control of lexical features; rare minor errors occur only as 'slips'.
Band 8: Uses a wide range of vocabulary fluently and flexibly to convey precise meanings. Skilfully uses uncommon lexical items; occasional inaccuracies in word choice and collocation. Produces rare errors in spelling and/or word formation.
Band 7: Uses a sufficient range of vocabulary to allow some flexibility and precision. Uses less common lexical items with some awareness of style and collocation. May produce occasional errors in word choice, spelling, and/or word formation.
Band 6: Uses an adequate range of vocabulary for the task. Attempts to use less common vocabulary but with some inaccuracy. Makes some errors in spelling and/or word formation but they do not impede communication.
Band 5: Uses a limited range of vocabulary, but this is minimally adequate for the task. May make noticeable errors in spelling and/or word formation that may cause some difficulty for the reader.

### Grammatical Range and Accuracy (GRA)
Band 9: Uses a wide range of structures with full flexibility and accuracy; rare minor errors occur only as 'slips'.
Band 8: Uses a wide range of structures. The majority of sentences are error-free. Makes only very occasional errors or inappropriacies.
Band 7: Uses a variety of complex structures. Produces frequent error-free sentences. Has good control of grammar and punctuation but may make a few errors.
Band 6: Uses a mix of simple and complex sentence forms. Makes some errors in grammar and punctuation but they rarely reduce communication.
Band 5: Uses only a limited range of structures. Attempts complex sentences but these tend to be less accurate than simple sentences. May make frequent grammatical errors; punctuation may be faulty.
"""

# ── Essay-type-specific task completion instructions ──────────────────────────

TASK_COMPLETION_BY_TYPE = {
    "opinion": """
Task completion checks for OPINION essay ("To what extent do you agree or disagree?"):
- Does the writer maintain a clear position THROUGHOUT the essay (not just in conclusion)?
- Are arguments supported with specific evidence, not vague generalizations?
- Does the writer address the full extent (completely agree, partially, disagree)?
- If partially agreeing, are BOTH sides given fair treatment?
- Cap TR at 6.0 if position only appears in conclusion.
- Cap TR at 5.5 if no clear position is discernible.""",

    "discussion": """
Task completion checks for DISCUSSION essay ("Discuss both views and give your own opinion."):
- Are BOTH views genuinely discussed (not just mentioned then dismissed)?
- Does the writer give their OWN opinion (not just summarize others')?
- Is each view supported with reasons/examples?
- Cap TR at 6.0 if own opinion is missing or only appears as afterthought.
- Cap TR at 5.5 if only one view is discussed.""",

    "problem_solution": """
Task completion checks for PROBLEM-SOLUTION essay:
- Are REAL, specific problems identified (not just restating the topic)?
- Are PRACTICAL, specific solutions proposed (not just "the government should do something")?
- Are problems and solutions balanced (not all problems, one-line solutions)?
- Cap TR at 6.0 if solutions are vague or generic.
- Cap TR at 5.5 if either problems or solutions section is missing.""",

    "advantages_disadvantages": """
Task completion checks for ADVANTAGES-DISADVANTAGES essay:
- Are BOTH advantages and disadvantages discussed with specific support?
- If asked "Do the advantages outweigh the disadvantages?", is a clear judgment given?
- Are points developed beyond listing (explanation + example)?
- Cap TR at 6.0 if judgment is missing when required.
- Cap TR at 5.5 if only one side is covered.""",

    "two_part": """
Task completion checks for TWO-PART QUESTION essay:
- Are BOTH questions addressed substantially (not one fully, one briefly)?
- Is each question given roughly equal development?
- Cap TR at 6.0 if one question is only superficially addressed.
- Cap TR at 5.5 if one question is completely ignored.""",
}

# ── Harshness calibration instructions ────────────────────────────────────────

HARSHNESS_CALIBRATION = """
## Scoring Calibration — Be an Examiner, Not a Tutor

You are calibrating your scores to match a STRICT IELTS examiner, not a helpful teacher.

CRITICAL RULES:
1. Do NOT reward vague examples. "For example, many people..." with no specifics = weak support.
2. Do NOT reward memorized introductions. "In today's modern world..." or "This essay will discuss..." = Band 5–6 formula.
3. Do NOT inflate scores for fluent but underdeveloped writing. Length and fluency ≠ depth.
4. Do NOT give Band 7+ for TR unless ALL parts of the task are FULLY addressed with DEVELOPED ideas.
5. If word count < 250 words, apply -0.5 to -1.0 penalty on Task Response.
6. If essay is off-topic or only tangentially related, cap TR at 5.0.
7. Mechanical cohesive devices ("Furthermore", "Moreover", "In addition" every paragraph) = Band 6 CC at best.
8. Repetitive vocabulary across paragraphs limits LR to 6.0 maximum.
9. Simple sentence structures dominating = GRA capped at 6.0 even if error-free.
10. A truly Band 8+ essay is rare — it requires sophisticated, precise, well-developed writing throughout.

COMMON INFLATION TRAPS TO AVOID:
- Essay reads smoothly but says nothing specific → max Band 6.5 overall
- Complex grammar attempted but frequently incorrect → GRA 5.5–6.0, not higher
- Good vocabulary but wrong collocations → LR 6.0, not 6.5
- Both views mentioned but not developed → TR 6.0 for discussion essay
"""

# ── Layer A+B: Scoring prompt ────────────────────────────────────────────────

SCORING_SYSTEM_PROMPT = """You are a senior IELTS Writing examiner with 15+ years of experience.
Score this Task 2 essay STRICTLY using the official IELTS band descriptors below.
You must quote direct evidence from the essay for every score you assign.

{band_descriptors}

{task_completion_instructions}

{harshness_calibration}

## Instructions

1. Read the essay carefully in relation to the ORIGINAL PROMPT.
2. For each of the 4 criteria, assign a band score (whole or .5 increments, range 4.0–9.0).
3. For each criterion, quote 1–3 specific excerpts from the essay as evidence.
4. For Task Response, also evaluate the task_completion flags.
5. Calculate overall_band as the arithmetic mean of all 4 criteria, rounded to nearest 0.5.
6. Write a coaching summary: 1–2 sentence overview, 2–3 strengths, 2–3 improvements.

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
1. Return EXACTLY 6–8 annotations. Prioritize BAND-AFFECTING issues over cosmetic ones.
2. Each annotation must include character offsets (start_char, end_char) measured from the START of the essay text.
3. Categories: grammar, vocabulary, spelling, punctuation, coherence, style
4. Severity: "major" (affects band score) or "minor" (worth noting but doesn't change band)
5. Suggestions must be specific and actionable — not "improve this" but "use 'exacerbate' instead of 'make worse'"
6. Do NOT annotate every small error. Focus on patterns that hurt the band score most.
7. Prioritize: grammar errors > vocabulary imprecision > coherence issues > spelling > punctuation > style

## Scoring context (use this to focus annotations on band-limiting issues)
Task Response: {tr_band} | Coherence: {cc_band} | Lexical: {lr_band} | Grammar: {gra_band}

## Output Format (strict JSON array, no markdown)

[
  {{
    "start_char": <int>,
    "end_char": <int>,
    "original_text": "<exact substring from essay>",
    "category": "<grammar|vocabulary|spelling|punctuation|coherence|style>",
    "suggestion": "<specific fix or alternative>",
    "severity": "<major|minor>"
  }}
]

IMPORTANT: start_char and end_char are 0-based character indices into the essay text.
Verify that essay[start_char:end_char] == original_text for each annotation.
"""


class WritingGrader:
    """3-layer evidence-based IELTS Writing Task 2 grader using GPT-4o."""

    GRADER_VERSION = "1.0"

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o"

    def grade(self, essay: str, prompt_data: dict) -> dict:
        """Full grading pipeline. Returns examiner result + coaching + annotations."""
        # Layer A+B: rubric analysis + score decision
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
        """Layer A+B: Score all 4 criteria with evidence quotes."""
        essay_type = prompt_data.get("essay_type", "opinion")
        task_instructions = TASK_COMPLETION_BY_TYPE.get(
            essay_type, TASK_COMPLETION_BY_TYPE["opinion"]
        )

        system_prompt = SCORING_SYSTEM_PROMPT.format(
            band_descriptors=BAND_DESCRIPTORS,
            task_completion_instructions=task_instructions,
            harshness_calibration=HARSHNESS_CALIBRATION,
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

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        scoring = json.loads(raw)

        # Validate overall_band is correct average
        er = scoring.get("examiner_result", {})
        bands = [
            er.get("task_response", {}).get("band", 0),
            er.get("coherence_cohesion", {}).get("band", 0),
            er.get("lexical_resource", {}).get("band", 0),
            er.get("grammatical_range_accuracy", {}).get("band", 0),
        ]
        computed = round(sum(bands) / 4 * 2) / 2  # round to nearest 0.5
        er["overall_band"] = computed

        return scoring

    def _annotate_errors(self, essay: str, prompt_data: dict, scoring: dict) -> list:
        """Layer C: 6–8 high-value annotations with character offsets."""
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

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            max_tokens=1500,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        parsed = json.loads(raw)

        # Handle both {"annotations": [...]} and bare [...]
        if isinstance(parsed, dict):
            annotations = parsed.get("annotations", [])
        elif isinstance(parsed, list):
            annotations = parsed
        else:
            annotations = []

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
                    # Try to find the original_text in the essay
                    idx = essay.find(original)
                    if idx >= 0:
                        ann["start_char"] = idx
                        ann["end_char"] = idx + len(original)
                    else:
                        # Skip annotations we can't locate
                        continue
            elif original:
                # No offsets provided — find by text
                idx = essay.find(original)
                if idx >= 0:
                    ann["start_char"] = idx
                    ann["end_char"] = idx + len(original)
                else:
                    continue

            validated.append(ann)

        return validated[:8]  # Cap at 8
