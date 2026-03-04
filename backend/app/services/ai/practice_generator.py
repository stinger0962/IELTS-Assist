import json
import random
from datetime import datetime
from openai import OpenAI
from app.config import settings

GENERATION_PROMPT = '''You are an IELTS Academic Reading item writer.

Your task is to generate ONE original mini IELTS Academic Reading practice set
targeting Band 6.5 difficulty.

CRITICAL RULES:
1. The passage and questions MUST be completely original.
2. Do NOT copy or paraphrase any known IELTS, Cambridge, or published material.
3. Invent all names, institutions, locations, statistics, and studies.
4. The content must feel realistic but fictional.
5. The output must follow the JSON schema exactly.
6. Do not include explanations outside the JSON.

Generation Context:
- Date: {date}
- Random Seed: {seed}
- Optional Topic Hint: {topic_hint}

Use the random seed to influence topic choice, setting, names, numerical data,
sub-arguments, and distractor patterns.

If Topic Hint is blank, randomly select an academic-style topic such as:
urban planning, environmental policy, behavioural psychology, education systems,
workplace productivity, digital privacy, public health trends, renewable energy
adoption, migration patterns, language development, or scientific research methodology.

--------------------------------------------------

TARGET SPECIFICATIONS (Band 6.5):

Passage:
- Length: 380-450 words
- Academic tone but accessible
- Clear paragraph structure (4-6 paragraphs)
- Moderate paraphrasing density
- Include at least 6 paraphrase relationships, 2 hedging expressions
  (e.g. "may", "appears to", "suggests"), and 1 contrast structure
  (however, although, while)

Question Types (include EXACTLY 2 types):
1) TRUE / FALSE / NOT GIVEN (5 questions)
2) Matching Headings OR Multiple Choice (3 questions)

Requirements for T/F/NG:
- Exactly: 2 TRUE, 2 FALSE, 1 NOT GIVEN
- The NOT GIVEN must be plausible but not stated.
- FALSE answers must contradict explicitly.

Requirements for Multiple Choice (if selected):
- 3 questions, 4 options each (A-D)
- One clearly correct, 2 plausible distractors, 1 obviously wrong

Requirements for Matching Headings (if selected):
- 5 headings total (A-E), only 3 are correct matches, 2 are distractors
- 3 paragraph titles for the reader to match

--------------------------------------------------

OUTPUT FORMAT (STRICT JSON ONLY):

{{
  "meta": {{
    "module": "IELTS Academic Reading",
    "target_band": 6.5,
    "word_count": integer,
    "topic": "string"
  }},
  "passage": "Full passage text with paragraph breaks as \\n\\n",
  "questions": {{
    "true_false_not_given": [
      {{"question_number": 1, "statement": "string"}},
      {{"question_number": 2, "statement": "string"}},
      {{"question_number": 3, "statement": "string"}},
      {{"question_number": 4, "statement": "string"}},
      {{"question_number": 5, "statement": "string"}}
    ],
    "second_type": {{
      "type": "multiple_choice OR matching_headings",
      "items": "SEE EXACT FORMAT BELOW"
    }}
  }},
  "answer_key": {{
    "true_false_not_given": [
      {{"question_number": 1, "answer": "TRUE or FALSE or NOT GIVEN"}}
    ],
    "second_type_answers": "SEE EXACT FORMAT BELOW"
  }}
}}

EXACT FORMAT when second_type is "multiple_choice":
  "items": [
    {{
      "question_number": 6,
      "question": "string",
      "options": {{"A": "string", "B": "string", "C": "string", "D": "string"}}
    }},
    {{
      "question_number": 7,
      "question": "string",
      "options": {{"A": "string", "B": "string", "C": "string", "D": "string"}}
    }},
    {{
      "question_number": 8,
      "question": "string",
      "options": {{"A": "string", "B": "string", "C": "string", "D": "string"}}
    }}
  ]
  "second_type_answers": [
    {{"question_number": 6, "answer": "A or B or C or D"}},
    {{"question_number": 7, "answer": "A or B or C or D"}},
    {{"question_number": 8, "answer": "A or B or C or D"}}
  ]

EXACT FORMAT when second_type is "matching_headings":
  "items": {{
    "headings": [
      {{"id": "A", "text": "string"}},
      {{"id": "B", "text": "string"}},
      {{"id": "C", "text": "string"}},
      {{"id": "D", "text": "string"}},
      {{"id": "E", "text": "string"}}
    ],
    "paragraphs": [
      {{"number": 1, "title": "string (first few words of the paragraph)"}},
      {{"number": 2, "title": "string"}},
      {{"number": 3, "title": "string"}}
    ]
  }}
  "second_type_answers": [
    {{"paragraph_number": 1, "answer": "A or B or C or D or E"}},
    {{"paragraph_number": 2, "answer": "A or B or C or D or E"}},
    {{"paragraph_number": 3, "answer": "A or B or C or D or E"}}
  ]

DO NOT include explanations, rationales, or extra commentary.
Return JSON only.'''

VALIDATION_PROMPT = '''Evaluate this IELTS Reading practice for:
1. Ambiguity in T/F/NG answers
2. Incorrect T/F/NG distribution (must be exactly 2 TRUE, 2 FALSE, 1 NOT GIVEN)
3. Missing explicit contradiction for FALSE answers
4. Whether NOT GIVEN is truly unstated in the passage
5. Schema compliance (items format matches the declared type)

Return JSON only:
{{
  "valid": boolean,
  "issues": ["issue1", "issue2"],
  "estimated_band": number,
  "recommendations": ["rec1"]
}}'''


class PracticeGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"

    def generate_practice(self, topic_hint: str = "") -> dict:
        """Generate a single practice with two-round validation"""
        date = datetime.now().strftime("%Y-%m-%d")
        seed = random.randint(1000, 9999)

        generation_result = self._generate(date, seed, topic_hint)
        if not generation_result:
            return None

        validation_result = self._validate(generation_result)

        attempts = 0
        while not validation_result.get("valid", False) and attempts < 3:
            attempts += 1
            generation_result = self._generate(date, seed + attempts * 100, topic_hint)
            if generation_result:
                validation_result = self._validate(generation_result)

        return generation_result

    def _generate(self, date: str, seed: int, topic_hint: str) -> dict:
        prompt = GENERATION_PROMPT.format(
            date=date,
            seed=seed,
            topic_hint=topic_hint or "random"
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS test writer. Generate valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=4000
            )
            content = response.choices[0].message.content
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return None
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
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return {"valid": False, "issues": ["Failed to parse validation response"]}
        except Exception as e:
            print(f"Validation error: {e}")
            return {"valid": False, "issues": [str(e)]}


# Singleton instance
practice_generator = PracticeGenerator()
