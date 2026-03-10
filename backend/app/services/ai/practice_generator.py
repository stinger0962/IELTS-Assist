import json
import random
from datetime import datetime
from openai import OpenAI
from app.config import settings
from app.services.ai.reading_config import generate_metadata

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
        """Generate a single practice with validation.

        Args:
            topic_hint: Legacy parameter (ignored if avoid_topics provided).
            avoid_topics: List of recently used topics to avoid.
        """
        # Build avoidance list from either parameter
        if avoid_topics is None and topic_hint and topic_hint.startswith("avoid:"):
            avoid_topics = [t.strip() for t in topic_hint.replace("avoid:", "").split(",") if t.strip()]

        attempts = 0
        while attempts < 3:
            attempts += 1
            metadata = generate_metadata(avoid_topics=avoid_topics)
            result = self._generate(metadata)
            if not result:
                continue

            validation = self._validate(result)
            if validation.get("valid", False):
                return result

        # Return last result even if validation didn't pass (better than nothing)
        return result if result else None

    def _generate(self, metadata: dict) -> dict:
        """Single GPT call: generate passage + questions using pre-selected metadata."""
        # Format numbers for prompt
        numbers_str = ", ".join(
            f"{k.replace('_', ' ')} = {v}" for k, v in metadata["numbers"].items()
        )

        # Format blueprint
        blueprint_str = " → ".join(metadata["blueprint"])

        # Format question composition description
        comp_parts = []
        for qtype, count in metadata["question_composition"]:
            label = qtype.replace("_", " ").title()
            comp_parts.append(f"{count} {label}")
        comp_str = ", ".join(comp_parts)
        total_q = metadata["total_questions"]

        # Format synonym distances
        distances = metadata["synonym_distances"]
        dist_str = ", ".join(f"Q{i+1}=L{d}" for i, d in enumerate(distances))

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

        # Append question generation instructions to same call (Phase 1: still single call)
        prompt += f'''

---

Now generate questions for the passage you wrote.

STEP 1 — Create paraphrase anchors
Identify 6 to 8 key factual anchor statements from the passage.
Each anchor must:
- be clearly supported by the passage
- be important enough to test
- be paraphrasable
- support a definitive answer

STEP 2 — Plan the questions
Create {total_q} questions using this mix: {comp_str}

Question rules:
- Questions should generally follow passage order unless the question type naturally does not
- Do not repeat more than three consecutive words from the passage
- Questions must be based on anchor statements
- Include plausible distractors where needed
- Completion questions must include strict word limits when appropriate

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
- Provide a summary paragraph with numbered blanks (___6___, ___7___), answers are 1-3 words from passage

For Short Answer:
- Provide a question, answer in 1-3 words from the passage

STEP 3 — Apply synonym distance control
For each question, paraphrase the anchor using a controlled distance level:
- Level 2: standard synonym substitution
- Level 3: grammatical transformation
- Level 4: structural paraphrase
- Level 5: conceptual paraphrase

Question synonym distances: {dist_str}
Avoid overly obvious wording overlap.

STEP 4 — Generate the answer key
For each question provide:
- the correct answer
- a brief explanation showing why the answer is correct

---

Return the COMPLETE output as STRICT JSON:
{{
  "meta": {{
    "module": "IELTS Academic Reading",
    "target_band": 6.5,
    "word_count": integer,
    "topic": "string"
  }},
  "passage": "Full passage text with paragraph breaks as \\n\\n",
  "questions": {{
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

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS test writer. Generate valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=6000
            )
            content = response.choices[0].message.content
            return self._parse_json(content)
        except Exception as e:
            print(f"Generation error: {e}")
            return None

    def _validate(self, practice: dict) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS test validator. Return valid JSON only."},
                    {"role": "user", "content": f"{VALIDATION_PROMPT}\n\nPractice to evaluate:\n{json.dumps(practice)}"}
                ],
                temperature=0.3,
                max_tokens=500
            )
            content = response.choices[0].message.content
            result = self._parse_json(content)
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
