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
- Recently Used Topics (AVOID these): {topic_hint}

Use the random seed to drive ALL four selection steps below.
If "Recently Used Topics" lists any topics, do NOT choose them — pick something different.

--------------------------------------------------

STEP 1 — SELECT ONE MAIN TOPIC

Use the seed to pick exactly ONE topic from the pool below.
Do NOT repeat any topic listed in "Recently Used Topics" above.

TOPIC POOL (100 topics):

Urban & Infrastructure:
  1. Urban heat island effects, 2. Smart city planning,
  3. Public transportation policy, 4. Affordable housing strategies,
  5. Green roof implementation, 6. Pedestrian-friendly city design,
  7. Urban waste management systems, 8. Disaster-resilient infrastructure,
  9. Coastal city flood defenses, 10. Mixed-use development models

Environment & Sustainability:
  11. Rewilding initiatives, 12. Ocean plastic mitigation,
  13. Carbon offset programs, 14. Sustainable agriculture models,
  15. Soil degradation research, 16. Deforestation monitoring,
  17. Biodiversity corridors, 18. Urban tree canopy impact,
  19. Water conservation technologies, 20. Climate migration patterns

Psychology & Behavioural Science:
  21. Habit formation research, 22. Decision fatigue theory,
  23. Social conformity experiments, 24. Risk perception studies,
  25. Memory retention techniques, 26. Emotional regulation strategies,
  27. Attention span in the digital age, 28. Motivation in workplace settings,
  29. Cognitive bias in policymaking, 30. Group dynamics research

Education Systems:
  31. Online vs traditional learning, 32. Assessment reform policies,
  33. Early childhood literacy, 34. Bilingual education models,
  35. Teacher training reforms, 36. Educational technology adoption,
  37. Standardized testing debates, 38. Lifelong learning initiatives,
  39. STEM curriculum development, 40. Academic performance inequality

Workplace & Economics:
  41. Remote work productivity, 42. Gig economy regulation,
  43. Workplace automation, 44. Corporate sustainability reporting,
  45. Organizational leadership styles, 46. Employee well-being programs,
  47. Small business resilience, 48. Innovation management theory,
  49. Gender pay gap studies, 50. Economic impact of tourism

Technology & Society:
  51. Data privacy regulations, 52. Artificial intelligence ethics,
  53. Social media misinformation, 54. Digital divide research,
  55. Cybersecurity awareness, 56. Biometric authentication systems,
  57. Smart home technology adoption, 58. E-commerce consumer behavior,
  59. Algorithmic bias, 60. Virtual reality in education

Public Health & Medicine:
  61. Vaccination outreach strategies, 62. Mental health stigma reduction,
  63. Aging population challenges, 64. Preventative healthcare models,
  65. Urban air pollution health impact, 66. Nutritional policy reforms,
  67. Sleep research findings, 68. Workplace stress interventions,
  69. Community fitness initiatives, 70. Telemedicine expansion

Science & Research:
  71. Citizen science projects, 72. Interdisciplinary research models,
  73. Research funding allocation, 74. Scientific peer review systems,
  75. Space exploration funding debates, 76. Renewable battery innovation,
  77. Water purification breakthroughs, 78. Agricultural biotechnology,
  79. Wildlife tracking technology, 80. Archaeological excavation methods

Society & Culture:
  81. Language preservation efforts, 82. Cultural heritage tourism,
  83. Migration integration policies, 84. Aging rural communities,
  85. Urban youth subcultures, 86. Volunteerism trends,
  87. Public art programs, 88. Community gardening projects,
  89. Media influence on public opinion, 90. Cultural adaptation in global cities

Policy & Governance:
  91. Evidence-based policymaking, 92. Public consultation models,
  93. Regulatory reform processes, 94. International climate agreements,
  95. Local governance innovation, 96. Transparency initiatives,
  97. Disaster response coordination, 98. Education funding distribution,
  99. Public housing allocation, 100. Infrastructure investment priorities

--------------------------------------------------

STEP 2 — SELECT ONE SUB-ANGLE

Use the seed to pick ONE analytical angle:
  Policy impact | Economic consequences | Psychological effects |
  Technological influence | Social implications | Environmental impact |
  Historical evolution | Ethical debate | Implementation challenges |
  Long-term projections

--------------------------------------------------

STEP 3 — SELECT ONE REGION CONTEXT

Use the seed to pick ONE region:
  Mid-sized European city | Rapidly developing Asian country |
  Coastal North American city | Rural South American community |
  Sub-Saharan African urban center | Australian regional town |
  Scandinavian capital | Middle Eastern metropolitan area |
  Small island nation | Fictional but realistic global setting

--------------------------------------------------

STEP 4 — SELECT ONE RESEARCH FRAMING

Use the seed to pick ONE research element:
  University-led longitudinal study | Government policy trial |
  NGO field report | Private sector pilot program |
  Comparative international study | Survey of 1,000+ participants |
  Historical data analysis | Experimental lab-based study |
  Community-based intervention | Meta-analysis of previous findings

--------------------------------------------------

Combine all 4 selections into a coherent academic passage.
Example: "Urban heat island effects" + "Policy impact" + "Mid-sized European city"
+ "University-led longitudinal study" → a passage about a university study
examining how urban heat island policy reduced temperatures in a mid-sized
European city.

If the combination feels too abstract or too narrow, regenerate internally
until you reach an appropriate, Band 6.5-suitable combination.

The "topic" field in the JSON meta should be the MAIN TOPIC name from Step 1
(e.g. "Urban heat island effects"), not a sentence.

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
            topic_hint=topic_hint or "none — choose freely from the 100-topic pool"
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
