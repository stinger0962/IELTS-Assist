import json
import random
from datetime import datetime
from openai import OpenAI
from app.config import settings
from app.services.ai.reading_config import generate_metadata

# ─── Step 1: Passage Generation ─────────────────────────────────────────────

PASSAGE_PROMPT = '''You are an expert IELTS Academic Reading passage writer.

Write an IELTS Academic reading passage with these requirements:
- 550 to 700 words
- 5 paragraphs
- Band 6.5 difficulty
- neutral academic tone
- B2 to low C1 vocabulary
- include at least one comparison
- include at least one research finding
- include at least one cause-effect relationship
- include realistic details and numerical data where natural
- do not make the passage overly technical or overly simple

Context (pre-selected by system):
- Topic: {topic}
- Angle: {angle}
- Text structure: {structure}
- Geographic context: {region}
- Research context: {research}
- Stakeholder perspective: {stakeholder}
- Evidence type: {evidence}
- Paragraph blueprint: {blueprint}
- Key data to embed: {numbers}

All names, institutions, locations must be fictional but realistic.

Return STRICT JSON only:
{{
  "passage": "Full passage text with paragraph breaks as \\n\\n",
  "meta": {{
    "word_count": integer,
    "topic": "string (the main topic name)"
  }}
}}

Do not include explanations outside the JSON.'''

# ─── Step 2: Question Generation ─────────────────────────────────────────────

QUESTIONS_PROMPT = '''You are an expert IELTS Academic Reading question writer.

Given this IELTS Academic Reading passage, generate questions following these steps.

STEP 1 — Create paraphrase anchors
Identify 6 to 8 key factual anchor statements from the passage.
Each anchor must:
- be clearly supported by the passage
- be important enough to test
- be paraphrasable
- support a definitive answer

STEP 2 — Plan the questions
Create {total_questions} questions using this mix: {composition}

Question rules:
- Questions should generally follow passage order unless the question type naturally does not
- Do not repeat more than three consecutive words from the passage
- Do not create questions that repeat the same noun phrase appearing next to the answer in the passage
- Questions must be based on anchor statements
- Each question must test a DIFFERENT anchor — no two questions across any groups may share the same answer or test the same fact
- Include plausible distractors where needed
- Completion questions must include strict word limits when appropriate

Rules for numeric information:
- Do NOT ask direct short-answer questions for numbers, percentages, dates, or quantities (e.g. "What percentage increase occurred?")
- Numbers should only be tested inside sentence completion, summary completion, or table completion where the surrounding wording is paraphrased
- At least one question should test the meaning or implication of numerical data rather than asking for the number itself

For True / False / Not Given:
- TRUE = directly supported by the passage
- FALSE = directly contradicted by the passage
- NOT GIVEN = cannot be confirmed or denied from the passage
- Include a mix (not all TRUE or all FALSE)

For Multiple Choice:
- 4 options (A-D), one clearly correct, plausible distractors

For Matching Headings:
- Provide a pool of headings (count + 2 distractors), student matches to paragraphs

For Matching Information:
- Provide statements, student matches each to a paragraph label (A, B, C, D, E)

For Sentence Completion:
- Provide a sentence with ___ blank, answer is 1-3 words from the passage

For Summary Completion:
- Provide a summary paragraph with numbered blanks (___N___), answers are 1-3 words from passage

For Short Answer:
- Provide a question, answer in 1-3 words from the passage
- Do NOT ask for a number, percentage, date, or quantity as a short answer

STEP 3 — Apply synonym distance control
For each question, paraphrase the anchor using a controlled distance level:
- Level 2: standard synonym substitution
- Level 3: grammatical transformation
- Level 4: structural paraphrase
- Level 5: conceptual paraphrase

Question synonym distances: {distances}
Avoid overly obvious wording overlap.

STEP 4 — Generate the answer key
For each question provide:
- the correct answer (must be unique — no two questions should have the same answer text)
- a brief explanation showing why the answer is correct

Passage:
{passage}

---

Return STRICT JSON only:
{{
  "groups": [
    {{
      "type": "true_false_not_given",
      "items": [
        {{"question_number": 1, "statement": "string", "answer": "TRUE or FALSE or NOT GIVEN", "explanation": "string"}}
      ]
    }},
    {{
      "type": "multiple_choice",
      "items": [
        {{"question_number": N, "question": "string", "options": {{"A": "string", "B": "string", "C": "string", "D": "string"}}, "answer": "A or B or C or D", "explanation": "string"}}
      ]
    }}
  ]
}}

For summary_completion groups, use this format:
{{
  "type": "summary_completion",
  "summary_text": "paragraph with ___N___ blanks",
  "items": [
    {{"question_number": N, "answer": "string", "word_limit": 3, "explanation": "string"}}
  ]
}}

For sentence_completion groups:
{{
  "type": "sentence_completion",
  "items": [
    {{"question_number": N, "text": "sentence with ___", "answer": "string", "word_limit": 3, "explanation": "string"}}
  ]
}}

For matching_headings groups:
{{
  "type": "matching_headings",
  "items": {{
    "headings": [{{"id": "A", "text": "string"}}, ...],
    "paragraphs": [{{"number": 1, "title": "first few words of paragraph"}}]
  }},
  "answers": [{{"paragraph_number": 1, "answer": "A", "explanation": "string"}}]
}}

For matching_information groups:
{{
  "type": "matching_information",
  "items": [
    {{"question_number": N, "statement": "string", "answer": "A or B or C or D or E", "explanation": "string"}}
  ]
}}

For short_answer groups:
{{
  "type": "short_answer",
  "items": [
    {{"question_number": N, "question": "string", "answer": "string", "word_limit": 3, "explanation": "string"}}
  ]
}}

Do NOT include anchors, reasoning, or commentary outside the JSON.
Return JSON only.'''

# ─── Validation ──────────────────────────────────────────────────────────────

VALIDATION_PROMPT = '''Validate this IELTS Reading practice output. Check:
- passage tone is IELTS-appropriate
- difficulty is close to Band 6.5
- questions are answerable from the passage
- no excessive wording overlap between passage and questions
- question types are varied
- answers are unambiguous
- word limits are respected for completion/short answer questions

Return JSON only:
{{
  "valid": boolean,
  "issues": ["issue1", "issue2"],
  "estimated_band": number
}}'''


class PracticeGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"

    def generate_practice(self, topic_hint: str = "", avoid_topics: list[str] | None = None) -> dict:
        """Generate a single reading practice via 2-step pipeline + validation.

        Step 1: Generate passage (GPT call #1)
        Step 2: Generate questions with paraphrase anchors (GPT call #2)
        Step 3: Validate (GPT call #3)
        """
        if avoid_topics is None and topic_hint and topic_hint.startswith("avoid:"):
            avoid_topics = [t.strip() for t in topic_hint.replace("avoid:", "").split(",") if t.strip()]

        result = None
        for attempt in range(3):
            metadata = generate_metadata(avoid_topics=avoid_topics)

            # Step 1: Generate passage
            passage_data = self._generate_passage(metadata)
            if not passage_data or not passage_data.get("passage"):
                continue

            # Step 2: Generate questions
            questions_data = self._generate_questions(metadata, passage_data["passage"])
            if not questions_data:
                continue

            # Merge into final result
            result = {
                "meta": {
                    "module": "IELTS Academic Reading",
                    "target_band": 6.5,
                    "word_count": passage_data.get("meta", {}).get("word_count", 0),
                    "topic": metadata["topic"],
                },
                "passage": passage_data["passage"],
                "questions": {
                    "groups": questions_data.get("groups", []),
                },
            }

            # Step 3: Validate
            validation = self._validate(result)
            if validation.get("valid", False):
                return result

        return result

    def _generate_passage(self, metadata: dict) -> dict | None:
        """GPT call #1: Generate the reading passage."""
        numbers_str = ", ".join(
            f"{k.replace('_', ' ')} = {v}" for k, v in metadata["numbers"].items()
        )
        blueprint_str = " → ".join(metadata["blueprint"])

        prompt = PASSAGE_PROMPT.format(
            topic=metadata["topic"],
            angle=metadata["angle"],
            structure=metadata["structure"],
            region=metadata["region"],
            research=metadata["research"],
            stakeholder=metadata["stakeholder"],
            evidence=metadata["evidence"],
            blueprint=blueprint_str,
            numbers=numbers_str,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS passage writer. Generate valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.85,
                max_tokens=3500,
            )
            return self._parse_json(response.choices[0].message.content)
        except Exception as e:
            print(f"Passage generation error: {e}")
            return None

    def _generate_questions(self, metadata: dict, passage: str) -> dict | None:
        """GPT call #2: Generate questions with paraphrase anchors + synonym distance."""
        comp_parts = []
        for qtype, count in metadata["question_composition"]:
            label = qtype.replace("_", " ").title()
            comp_parts.append(f"{count} {label}")
        comp_str = ", ".join(comp_parts)

        distances = metadata["synonym_distances"]
        dist_str = ", ".join(f"Q{i+1}=L{d}" for i, d in enumerate(distances))

        prompt = QUESTIONS_PROMPT.format(
            total_questions=metadata["total_questions"],
            composition=comp_str,
            distances=dist_str,
            passage=passage,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS question writer. Generate valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=3000,
            )
            return self._parse_json(response.choices[0].message.content)
        except Exception as e:
            print(f"Question generation error: {e}")
            return None

    def _validate(self, practice: dict) -> dict:
        """GPT call #3: Validate the complete practice."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS test validator. Return valid JSON only."},
                    {"role": "user", "content": f"{VALIDATION_PROMPT}\n\nPractice to evaluate:\n{json.dumps(practice)}"},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            result = self._parse_json(response.choices[0].message.content)
            return result if result else {"valid": False, "issues": ["Failed to parse validation response"]}
        except Exception as e:
            print(f"Validation error: {e}")
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
practice_generator = PracticeGenerator()
