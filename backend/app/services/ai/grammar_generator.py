"""Grammar exercise generation pipeline.

2-step process:
  Step 1: Generate context paragraph + exercises (GPT call #1)
  Step 2: Validate (GPT call #2)

Produces exercises with 3 exact-match question types:
  - error_correction: sentences with embedded errors, student types correction
  - gap_fill: blanks with base word hints, student types correct form
  - grammar_mcq: 4-option multiple choice testing grammar rules
"""

import json
from datetime import datetime
from openai import OpenAI
from app.config import settings
from app.services.ai.grammar_config import generate_metadata

# ─── Step 1: Context + Exercises Generation ──────────────────────────────────

GRAMMAR_PROMPT = '''You are an expert IELTS grammar exercise writer.

Create a grammar exercise targeting this grammar point:
- Grammar topic: {grammar_topic_name}
- Key pattern: {key_pattern}
- Common error: {common_error}
- Band level: {band_label}
- IELTS context theme: {context_theme}

STEP 1 — Write a grammar tip (2-3 sentences)
- Briefly explain the grammar rule being tested
- Include ONE clear example sentence demonstrating correct usage
- Keep it concise and learner-friendly

STEP 2 — Write a short IELTS-relevant context paragraph (80-150 words)
- The paragraph should be about the context theme
- It should naturally contain examples of the target grammar point
- Use B2 to low C1 vocabulary
- Academic but accessible tone

STEP 3 — Create {total_questions} questions using this mix: {composition}

For error_correction:
- Provide a sentence that contains ONE grammatical error related to the target grammar topic
- The error should be realistic (a common learner mistake)
- The sentence must be from an IELTS-relevant context
- Provide the incorrect sentence, the correct answer (full corrected sentence), and the specific error description
- Format: {{"question_number": N, "sentence": "sentence with error", "answer": "full corrected sentence", "error_description": "what the error is", "explanation": "why the correction is needed"}}

For gap_fill:
- Provide a sentence with ONE blank indicated by ___
- Include a base word hint in parentheses after the blank
- The answer should be the grammatically correct form of the hint word
- Each gap_fill sentence MUST be unique and original — do NOT reuse or adapt the format example below
- Format: {{"question_number": N, "sentence": "The ___ (sentence) with a blank and hint word", "hint": "base_word", "answer": "correct_form", "explanation": "grammar rule explanation"}}

For grammar_mcq:
- Provide a sentence or short context with 4 options (A-D)
- One option must be clearly correct; others should be plausible but grammatically wrong
- The question should test understanding of the grammar rule, not just vocabulary
- IMPORTANT: If the question contains a blank (___), the options must complete the blank seamlessly — the correct option must NOT repeat words already adjacent to the blank. For example, "This is the ___ preserved" with option "most well-preserved" would result in "most well-preserved preserved" — this is WRONG. Instead, use "the ___ artifact" with option "most well-preserved".
- Format: {{"question_number": N, "question": "Choose the correct option: ...", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "answer": "A", "explanation": "..."}}

IMPORTANT RULES:
- All questions must target the specified grammar topic
- Errors and distractors should reflect the common_error pattern
- Each question must be distinct — do not repeat the same sentence or test the same specific usage
- Explanations must name the grammar rule being tested
- Sentences should use IELTS-relevant academic vocabulary and topics

Return STRICT JSON only:
{{
  "grammar_tip": "Brief explanation of the grammar rule + one example sentence.",
  "highlight_phrases": ["phrase from context 1", "phrase from context 2"],
  "context": "the context paragraph text",
  "meta": {{
    "grammar_topic": "{grammar_topic_name}",
    "band_level": "{band_label}",
    "context_theme": "{context_theme}",
    "question_count": {total_questions}
  }},
  "questions": {{
    "groups": [
      {{
        "type": "error_correction",
        "items": [...]
      }},
      {{
        "type": "gap_fill",
        "items": [...]
      }},
      {{
        "type": "grammar_mcq",
        "items": [...]
      }}
    ]
  }}
}}

The "highlight_phrases" array must contain the EXACT phrases or words from the context paragraph that demonstrate the target grammar point. These will be highlighted in the UI so the learner can see the grammar in action.

Only include groups that have questions assigned. Do not include empty groups.
Do not include explanations outside the JSON. Return JSON only.'''

# ─── Step 2: Validation ──────────────────────────────────────────────────────

VALIDATION_PROMPT = '''Validate this IELTS Grammar exercise. Check:
- The context paragraph is grammatically correct and IELTS-appropriate
- All error_correction sentences contain exactly ONE error related to the target grammar topic
- All gap_fill answers are the correct grammatical form
- All MCQ options are plausible and the correct answer is unambiguous
- Explanations correctly name the grammar rule
- Questions are varied (not repetitive)
- Difficulty matches the stated band level

Return JSON only:
{{
  "valid": boolean,
  "issues": ["issue1", "issue2"],
  "estimated_band": number
}}'''


class GrammarGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"

    def generate(self, avoid_topics: list[str] | None = None) -> dict | None:
        """Generate a single grammar exercise via 2-step pipeline.

        Step 1: Generate context + exercises (GPT call #1)
        Step 2: Validate (GPT call #2)
        """
        result = None
        for attempt in range(3):
            metadata = generate_metadata(avoid_topics=avoid_topics)

            # Step 1: Generate exercises
            exercise_data = self._generate_exercises(metadata)
            if not exercise_data or not exercise_data.get("context"):
                continue

            # Merge metadata
            result = {
                "meta": {
                    "module": "IELTS Grammar Practice",
                    "grammar_topic": metadata["grammar_topic"]["name"],
                    "key_pattern": metadata["grammar_topic"]["key_pattern"],
                    "band_level": metadata["band_label"],
                    "context_theme": metadata["context_theme"],
                    "question_count": metadata["total_questions"],
                },
                "grammar_tip": exercise_data.get("grammar_tip", ""),
                "highlight_phrases": exercise_data.get("highlight_phrases", []),
                "context": exercise_data["context"],
                "questions": exercise_data.get("questions", {"groups": []}),
            }

            # Step 2: Validate
            validation = self._validate(result)
            if validation.get("valid", False):
                return result

        return result

    def _generate_exercises(self, metadata: dict) -> dict | None:
        """GPT call #1: Generate context paragraph + all exercise questions."""
        topic = metadata["grammar_topic"]

        comp_parts = []
        for qtype, count in metadata["exercise_composition"]:
            label = qtype.replace("_", " ").title()
            comp_parts.append(f"{count} {label}")
        comp_str = ", ".join(comp_parts)

        prompt = GRAMMAR_PROMPT.format(
            grammar_topic_name=topic["name"],
            key_pattern=topic["key_pattern"],
            common_error=topic["common_error"],
            band_label=metadata["band_label"],
            context_theme=metadata["context_theme"],
            total_questions=metadata["total_questions"],
            composition=comp_str,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS grammar exercise writer. Generate valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=3000,
            )
            return self._parse_json(response.choices[0].message.content)
        except Exception as e:
            print(f"Grammar generation error: {e}")
            return None

    def _validate(self, practice: dict) -> dict:
        """GPT call #2: Validate the complete grammar exercise."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS grammar validator. Return valid JSON only."},
                    {"role": "user", "content": f"{VALIDATION_PROMPT}\n\nExercise to evaluate:\n{json.dumps(practice)}"},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            result = self._parse_json(response.choices[0].message.content)
            return result if result else {"valid": False, "issues": ["Failed to parse validation response"]}
        except Exception as e:
            print(f"Grammar validation error: {e}")
            return {"valid": False, "issues": [str(e)]}

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        """Extract JSON from GPT response text."""
        if not text:
            return None
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            try:
                return json.loads(text[json_start:json_end])
            except json.JSONDecodeError:
                return None
        return None


# Singleton instance
grammar_generator = GrammarGenerator()
