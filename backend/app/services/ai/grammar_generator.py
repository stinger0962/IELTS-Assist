"""Grammar exercise generation pipeline.

2-step process:
  Step 1: Generate context paragraph + exercises (GPT call #1)
  Step 2: Validate (GPT call #2)

Produces exercises with 6 question types:
  - error_correction: sentences with embedded errors, student types correction
  - gap_fill: blanks with base word hints, student types correct form
  - grammar_mcq: 4-option multiple choice testing grammar rules
  - sentence_transformation: rewrite sentence using target grammar
  - sentence_combination: combine short sentences using target grammar
  - context_completion: fill grammar-focused gap in a paragraph
"""

import json
from datetime import datetime
from openai import OpenAI
from app.config import settings
from app.services.ai.grammar_config import generate_metadata

# ─── Step 1: Context + Exercises Generation ──────────────────────────────────

GRAMMAR_PROMPT_HEADER = '''You are an expert IELTS grammar exercise writer.

Create a grammar exercise targeting this grammar point:
- Grammar topic: {grammar_topic_name}
- Key pattern: {key_pattern}
- Common error: {common_error}
- Band level: {band_label}
- IELTS context theme: {context_theme}
- Sentence complexity: {sentence_complexity}
- Error focus: {error_type}
- Register: {register}
- Paraphrase distance: {paraphrase_distance}
- Cognitive difficulty: {cognitive_difficulty}
- Skill integration: {skill_integration}

STEP 1 — Write a grammar tip (2-3 sentences)
- Briefly explain the grammar rule being tested
- Include ONE clear example sentence demonstrating correct usage
- Keep it concise and learner-friendly

STEP 2 — Write an IELTS-relevant context paragraph (200-300 words)
- The paragraph should be about the context theme
- It should naturally contain multiple examples of the target grammar point
- Use B2 to low C1 vocabulary
- Write in the specified register (e.g. academic essay, news report, lecture transcript)
- Prefer the specified sentence complexity where natural
- Include enough grammar instances to demonstrate the pattern thoroughly

STEP 3 — Create {total_questions} questions using this mix: {composition}
(See format details below for each type.)

STEP 4 — Extract highlight phrases
After writing the context paragraph, go back and find ALL instances of the target grammar point in it.
List every occurrence as an exact substring copied from the context.
Do NOT invent phrases — only copy verbatim from the context you wrote in Step 2.

'''

# Per-type format specs — only included when the type appears in the composition
TYPE_SPECS = {
    "error_correction": '''For error_correction:
- Provide a sentence that contains ONE grammatical error related to the target grammar topic
- The error should be realistic (a common learner mistake)
- The sentence must be from an IELTS-relevant context
- Provide the incorrect sentence, the correct answer (full corrected sentence), and the specific error description
- Format: {{"question_number": N, "sentence": "sentence with error", "answer": "full corrected sentence", "error_description": "what the error is", "explanation": "why the correction is needed"}}
''',
    "gap_fill": '''For gap_fill:
- Provide a sentence with ONE blank indicated by ___
- Include a base word hint in parentheses after the blank
- The answer should be the grammatically correct form of the hint word
- Each gap_fill sentence MUST be unique and original — do NOT reuse or adapt the format example below
- Format: {{"question_number": N, "sentence": "The ___ (sentence) with a blank and hint word", "hint": "base_word", "answer": "correct_form", "explanation": "grammar rule explanation"}}
''',
    "grammar_mcq": '''For grammar_mcq:
- Provide a sentence or short context with 4 options (A-D)
- One option must be clearly correct; others should be plausible but grammatically wrong
- The question should test understanding of the grammar rule, not just vocabulary
- IMPORTANT: If the question contains a blank (___), the options must complete the blank seamlessly — the correct option must NOT repeat words already adjacent to the blank.
- Format: {{"question_number": N, "question": "Choose the correct option: ...", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "answer": "A", "explanation": "..."}}
''',
    "sentence_transformation": '''For sentence_transformation:
- Provide an original sentence and an instruction to rewrite it using the target grammar
- The instruction should be clear and specific (e.g. "Rewrite using passive voice", "Rewrite using a cleft sentence")
- The answer must be a grammatically correct transformation that preserves the original meaning
- Format: {{"question_number": N, "instruction": "Rewrite using [grammar structure]", "original_sentence": "The original sentence here.", "answer": "The transformed sentence here.", "explanation": "why this transformation applies the grammar rule"}}
''',
    "sentence_combination": '''For sentence_combination:
- Provide 2-3 short simple sentences and an instruction to combine them using the target grammar
- The combined sentence must use the target grammar point naturally
- Format: {{"question_number": N, "sentences": ["Short sentence one.", "Short sentence two."], "instruction": "Combine using [grammar structure]", "answer": "The combined sentence.", "explanation": "how the grammar connects these ideas"}}
''',
    "context_completion": '''For context_completion:
- Provide a short paragraph (2-3 sentences) with ONE blank (___) where the target grammar structure belongs
- Include a hint about what grammar structure to use
- The answer should be a short phrase (2-6 words) that completes the gap grammatically
- Format: {{"question_number": N, "paragraph": "A short paragraph with ___ a blank in it.", "hint": "use [grammar structure]", "answer": "the correct phrase", "explanation": "why this phrase fits grammatically"}}
''',
    "paraphrase_rewrite": '''For paraphrase_rewrite:
- Show an original sentence, then provide 4 paraphrase options (A-D) that use different grammar structures
- Only ONE option correctly paraphrases the meaning while using the target grammar point correctly
- Distractors should change meaning, use wrong grammar, or apply the grammar rule incorrectly
- IELTS design: test whether students recognise correct paraphrase under grammar transformation
- Format: {{"question_number": N, "original_sentence": "The original sentence.", "options": {{"A": "paraphrase A", "B": "paraphrase B", "C": "paraphrase C", "D": "paraphrase D"}}, "answer": "B", "explanation": "why this paraphrase correctly preserves meaning using the target grammar"}}
''',
    "grammar_function_id": '''For grammar_function_id:
- Show a sentence with a word or phrase highlighted using **bold markers** (e.g. "The team **quickly** adapted")
- Ask what grammatical function the highlighted element serves
- Provide 4 options (A-D) with grammatical function labels
- Only ONE option is correct; others should be plausible but wrong
- Format: {{"question_number": N, "sentence": "The team **quickly** adapted to the new system.", "question": "What is the grammatical function of the highlighted word?", "options": {{"A": "adverb of manner", "B": "adjective", "C": "adverb of frequency", "D": "intensifier"}}, "answer": "A", "explanation": "why this grammatical function is correct"}}
''',
}

GRAMMAR_PROMPT_FOOTER = '''IMPORTANT RULES:
- All questions must target the specified grammar topic
- Errors and distractors should reflect the common_error pattern
- Each question must be distinct — do not repeat the same sentence or test the same specific usage
- Explanations must name the grammar rule being tested
- Sentences should use IELTS-relevant academic vocabulary and topics

IELTS DESIGN PATTERNS (apply where natural):
- Paraphrase trap: MCQ options rephrase the grammar differently — only one preserves meaning correctly
- Structure shift: require the student to express the same idea using a different grammatical structure
- Function word gap: test articles, prepositions, or conjunctions that change meaning in context
- Controlled transformation: specify exactly which grammar rule the student must apply
- Parallel structure repair: include broken parallelism as a distractor or error

Return STRICT JSON only:
{{
  "grammar_tip": "Brief explanation of the grammar rule + one example sentence.",
  "context": "the context paragraph text",
  "highlight_phrases": ["exact phrase from context 1", "exact phrase from context 2", "...all occurrences"],
  "meta": {{
    "grammar_topic": "{grammar_topic_name}",
    "band_level": "{band_label}",
    "context_theme": "{context_theme}",
    "sentence_complexity": "{sentence_complexity}",
    "error_type": "{error_type}",
    "register": "{register}",
    "paraphrase_distance": "{paraphrase_distance}",
    "cognitive_difficulty": "{cognitive_difficulty}",
    "skill_integration": "{skill_integration}",
    "question_count": {total_questions}
  }},
  "questions": {{
    "groups": [
      {groups_example}
    ]
  }}
}}

CRITICAL — "highlight_phrases" rules:
- Scan the ENTIRE context paragraph and find ALL instances of the target grammar point
- Include EVERY occurrence, not just 1 or 2 — if the grammar appears 7 times, list all 7
- Each phrase must be the EXACT substring from the context (copy-paste, not paraphrased)
- Keep phrases short: just the grammar structure itself (e.g. "have been researched", "are taught"), not the full sentence
- For passive voice: highlight every "be + past participle" phrase
- For conditionals: highlight every "if... would/will" clause
- For articles: highlight every "a/an/the" + noun phrase
- The UI highlights these for learners, so completeness is essential

Only include groups that have questions assigned. Do not include empty groups.
Do not include explanations outside the JSON. Return JSON only.'''

# ─── Step 2: Validation ──────────────────────────────────────────────────────

VALIDATION_PROMPT = '''Validate this IELTS Grammar exercise. Check:
- The context paragraph is grammatically correct and IELTS-appropriate
- All error_correction sentences contain exactly ONE error related to the target grammar topic
- All gap_fill answers are the correct grammatical form
- All MCQ options are plausible and the correct answer is unambiguous
- All sentence_transformation answers correctly apply the specified grammar rule
- All sentence_combination answers properly combine sentences using the target grammar
- All context_completion answers fit grammatically in the paragraph
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
                    "sentence_complexity": metadata.get("sentence_complexity", ""),
                    "error_type": metadata.get("error_type", ""),
                    "register": metadata.get("register", ""),
                    "paraphrase_distance": metadata.get("paraphrase_distance", ""),
                    "cognitive_difficulty": metadata.get("cognitive_difficulty", ""),
                    "skill_integration": metadata.get("skill_integration", ""),
                    "question_count": metadata["total_questions"],
                },
                "grammar_tip": exercise_data.get("grammar_tip", ""),
                "highlight_phrases": self._validate_highlights(
                    exercise_data.get("highlight_phrases", []),
                    exercise_data["context"],
                ),
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

        # Build type specs — only include formats for types in this composition
        active_types = {qtype for qtype, _ in metadata["exercise_composition"]}
        type_specs_str = "\n".join(
            TYPE_SPECS[t] for t in active_types if t in TYPE_SPECS
        )

        # Build groups example for JSON template
        groups_example = ", ".join(
            f'{{{{"type": "{qtype}", "items": [...]}}}}'
            for qtype, _ in metadata["exercise_composition"]
        )

        format_args = dict(
            grammar_topic_name=topic["name"],
            key_pattern=topic["key_pattern"],
            common_error=topic["common_error"],
            band_label=metadata["band_label"],
            context_theme=metadata["context_theme"],
            sentence_complexity=metadata.get("sentence_complexity", "complex"),
            error_type=metadata.get("error_type", "substitution"),
            register=metadata.get("register", "academic_essay"),
            paraphrase_distance=metadata.get("paraphrase_distance", "medium"),
            cognitive_difficulty=metadata.get("cognitive_difficulty", "production"),
            skill_integration=metadata.get("skill_integration", "reading_grammar"),
            total_questions=metadata["total_questions"],
            composition=comp_str,
            groups_example=groups_example,
        )

        prompt = (
            GRAMMAR_PROMPT_HEADER.format(**format_args)
            + type_specs_str
            + "\n"
            + GRAMMAR_PROMPT_FOOTER.format(**format_args)
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS grammar exercise writer. Generate valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
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
    def _validate_highlights(phrases: list[str], context: str) -> list[str]:
        """Keep only phrases that actually appear in the context (case-insensitive).

        For phrases that don't match exactly, try to find them case-insensitively
        and return the exact substring from the context so highlighting works.
        """
        ctx_lower = context.lower()
        result = []
        for phrase in phrases:
            if phrase in context:
                result.append(phrase)
            elif phrase.lower() in ctx_lower:
                # Find the exact-case version from the context
                idx = ctx_lower.index(phrase.lower())
                result.append(context[idx:idx + len(phrase)])
            # else: phrase doesn't exist in context at all — drop it
        return result

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
