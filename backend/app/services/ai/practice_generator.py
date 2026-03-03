import json
import random
from datetime import datetime
from openai import OpenAI
from app.config import settings
import os

# Use OpenRouter - the API key is passed via environment variable
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

GENERATION_PROMPT = '''You are an IELTS Academic Reading item writer. Your task is to generate ONE original mini IELTS Academic Reading practice set targeting Band 6.5 difficulty. CRITICAL RULES: 1. The passage and questions MUST be completely original. 2. Do NOT copy or paraphrase any known IELTS, Cambridge, or published material. 3. Invent all names, institutions, locations, statistics, and studies. 4. The content must feel realistic but fictional. 5. The output must follow the JSON schema exactly. 6. Do not include explanations outside the JSON. Generation Context: - Date: {date} - Random Seed: {seed} - Optional Topic Hint: {topic_hint} Use the random seed to influence: - Topic choice - Setting - Names - Numerical data - Sub-arguments - Distractor patterns If Topic Hint is blank, randomly select an academic-style topic such as: urban planning, environmental policy, behavioural psychology, education systems, workplace productivity, digital privacy, public health trends, renewable energy adoption, migration patterns, language development, or scientific research methodology. -------------------------------------------------- TARGET SPECIFICATIONS (Band 6.5): Passage: - Length: 380–450 words - Academic tone but accessible - Clear paragraph structure (4–6 paragraphs) - Moderate paraphrasing density - Include: • At least 6 paraphrase relationships • At least 2 hedging expressions (e.g., may, appears to, suggests) • At least 1 contrast structure (however, although, while) Question Types (include EXACTLY 2 types): 1) TRUE / FALSE / NOT GIVEN (5 questions) 2) Matching Headings OR Multiple Choice (3 questions) Requirements for T/F/NG: - Exactly: • 2 TRUE • 2 FALSE • 1 NOT GIVEN - The NOT GIVEN must be plausible but not stated. - FALSE answers must contradict explicitly. Requirements for Matching Headings (if selected): - Provide 5 headings (A–E) - Only 3 are correct - 2 are distractors Requirements for Multiple Choice (if selected): - 3 questions - 4 options each (A–D) - One clearly correct - 2 plausible distractors - 1 obviously wrong distractor -------------------------------------------------- INTERNAL DIFFICULTY CONTROL: The passage should: - Require scanning and limited inference - Avoid overly abstract philosophical argument - Avoid highly technical terminology - Contain moderately complex sentences - Contain specific details (dates, percentages, names) -------------------------------------------------- OUTPUT FORMAT (STRICT JSON ONLY): {{ "meta": {{ "module": "IELTS Academic Reading", "target_band": 6.5, "word_count": integer, "topic": "string" }}, "passage": "Full passage text...", "questions": {{ "true_false_not_given": [ {{ "question_number": 1, "statement": "string" }} ], "second_type": {{ "type": "matching_headings OR multiple_choice", "items": [...] }} }}, "answer_key": {{ "true_false_not_given": [ {{ "question_number": 1, "answer": "TRUE / FALSE / NOT GIVEN" }} ], "second_type_answers": [...] }} }} DO NOT include explanations. DO NOT include rationales. DO NOT include extra commentary. Return JSON only.'''

VALIDATION_PROMPT = '''Evaluate this IELTS Reading practice for: 1. Ambiguity in answers 2. Incorrect T/F/NG distribution 3. Missing explicit contradiction for FALSE 4. Whether NOT GIVEN is truly unstated 5. Estimated band score Return JSON evaluation with format: {{ "valid": boolean, "issues": ["issue1", "issue2"], "estimated_band": number, "recommendations": ["rec1", "rec2"] }} If valid is false, the practice should be regenerated.'''


class PracticeGenerator:
    def __init__(self):
        # Use OpenRouter - cheaper and works in China
        self.client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
        # Using gpt-4o-mini - much cheaper than gpt-4o
        self.model = "openai/gpt-4o-mini"
    
    def generate_practice(self, topic_hint: str = "") -> dict:
        """Generate a single practice with two-round validation"""
        date = datetime.now().strftime("%Y-%m-%d")
        seed = random.randint(1000, 9999)
        
        # First round: Generate practice
        generation_result = self._generate(date, seed, topic_hint)
        
        if not generation_result:
            return None
        
        # Second round: Validate
        validation_result = self._validate(generation_result)
        
        # If validation fails, try again (max 3 attempts)
        attempts = 0
        while not validation_result.get("valid", False) and attempts < 3:
            attempts += 1
            # Generate new with different seed
            generation_result = self._generate(date, seed + attempts * 100, topic_hint)
            if generation_result:
                validation_result = self._validate(generation_result)
        
        return generation_result
    
    def _generate(self, date: str, seed: int, topic_hint: str) -> dict:
        """Generate practice using OpenRouter"""
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
            # Parse JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                return json.loads(json_str)
            return None
        except Exception as e:
            print(f"Generation error: {e}")
            return None
    
    def _validate(self, practice: dict) -> dict:
        """Validate the generated practice"""
        try:
            practice_str = json.dumps(practice)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS test validator. Return valid JSON only."},
                    {"role": "user", "content": f"{VALIDATION_PROMPT}\n\nPractice to evaluate:\n{practice_str}"}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                return json.loads(json_str)
            return {"valid": False, "issues": ["Failed to parse validation response"]}
        except Exception as e:
            print(f"Validation error: {e}")
            return {"valid": False, "issues": [str(e)]}


# Singleton instance
practice_generator = PracticeGenerator()
