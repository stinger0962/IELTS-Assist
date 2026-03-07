import json
import random
from datetime import datetime
from openai import OpenAI
from app.config import settings
from app.services.tts import synthesize, synthesize_dialogue, VOICE_PAIRS, VOICES

LISTENING_PROMPT = '''You are an IELTS Listening item writer.

Your task is to generate ONE original IELTS Listening practice set
targeting Band 6.5 difficulty.

CRITICAL RULES:
1. The transcript and questions MUST be completely original.
2. Do NOT copy any known IELTS, Cambridge, or published material.
3. Invent all names, institutions, locations, phone numbers, dates, and prices.
4. The content must feel realistic but fictional.
5. The output must follow the JSON schema exactly.
6. Do not include explanations outside the JSON.

Generation Context:
- Date: {date}
- Random Seed: {seed}
- Recently Used Topics (AVOID these): {topic_hint}

Use the random seed to drive ALL selection steps below.
If "Recently Used Topics" lists any topics, do NOT choose them.

--------------------------------------------------

STEP 1 — SELECT FORMAT

Use the seed to pick exactly ONE format:

  "conversation" → IELTS Part 1: 2 speakers in an everyday situation
  "monologue"    → IELTS Part 2: 1 speaker giving practical information
  "discussion"   → IELTS Part 3: 2 speakers in an academic context
  "lecture"       → IELTS Part 4: 1 speaker on an academic subject

--------------------------------------------------

STEP 2 — SELECT SCENARIO

For "conversation" (everyday, 2 speakers), pick ONE:
  Booking a hotel | Renting an apartment | Joining a gym |
  Arranging travel | Registering for a course | Making a restaurant reservation |
  Calling about a job | Booking a medical appointment | Enquiring about an event |
  Arranging home repairs | Signing up for a library | Reporting a lost item |
  Opening a bank account | Planning a birthday party | Buying a car

For "monologue" (everyday, 1 speaker), pick ONE:
  Tour guide describing a town | Museum audio guide |
  Welcome talk at orientation | Radio segment about a local event |
  Instructions for a competition | Speech at a community meeting |
  Announcement about facility changes | Presentation about a charity project |
  Talk about a historical site | Information about a transport service

For "discussion" (academic, 2 speakers), pick ONE:
  Reviewing a group project plan | Discussing research methodology |
  Comparing essay approaches | Debating a case study conclusion |
  Planning a field trip | Evaluating survey results |
  Preparing for a seminar presentation | Choosing dissertation topics |
  Analysing lab experiment data | Discussing internship experiences

For "lecture" (academic, 1 speaker), pick ONE:
  Introduction to marine ecosystems | History of urban planning |
  Principles of behavioural economics | Developments in renewable energy |
  Psychology of consumer decision-making | Climate change adaptation strategies |
  Evolution of public health policy | Impact of social media on journalism |
  Innovations in agricultural science | Archaeology and modern technology

--------------------------------------------------

STEP 3 — SELECT COMPLICATION / TWIST

Pick ONE to add realism and drive the dialogue:
  Change of plan | Budget constraint | Time conflict |
  Missing information | Special requirement | Unexpected closure |
  Discount or promotion | Recommendation from a friend |
  Medical or dietary need | Transport difficulty

--------------------------------------------------

STEP 4 — SELECT DETAIL FOCUS

Pick ONE category of specific facts to embed as answers:
  Dates and times | Prices and payments | Names and addresses |
  Phone numbers and emails | Room or seat numbers | Dietary preferences |
  Transport schedules | Equipment and materials | Membership tiers |
  Event schedules and deadlines

--------------------------------------------------

Combine all 4 selections into a coherent listening scenario.
Example: "Booking a hotel" + "Budget constraint" + "Dates and times"
→ A conversation where a guest books a hotel but the preferred room is
too expensive, so they negotiate dates to get a cheaper rate.

If the combination feels forced, adjust internally until natural.

The "topic" field should be a short scenario label (e.g. "Booking a hotel").

--------------------------------------------------

STEP 5 — WRITE TRANSCRIPT

For "conversation" or "discussion" (2 speakers):
- Use realistic names (e.g. "Sarah", "Receptionist", "Dr. Wilson", "Tom")
- Format EVERY line as: "SpeakerName: dialogue text"
- Each line is one speaker turn — alternate speakers naturally
- 400–500 words total
- Use natural spoken English: contractions, fillers ("well", "actually",
  "right", "so"), self-corrections ("I mean"), and brief hesitations
- Spread key answer details (names, numbers, dates, prices) evenly
  throughout the entire transcript — do NOT cluster them
- For "discussion": use academic vocabulary and reasoning language
  ("I think we should", "the data suggests", "on the other hand")

For "monologue" or "lecture" (1 speaker):
- Use a single speaker name (e.g. "Guide", "Professor Chen")
- Format as: "SpeakerName: dialogue text" (can be one long block or
  split into logical sections)
- 450–550 words total
- Organise into 2–3 clear sections with signpost language
  ("First of all", "Moving on to", "Finally")
- Use natural spoken style, not written essay style
- For "lecture": include academic examples, studies, and data points

IMPORTANT: The transcript must contain EXACT words/phrases that become
completion answers. Answers are heard literally in the audio.

--------------------------------------------------

STEP 6 — GENERATE QUESTIONS

Generate exactly 10 questions. The mix depends on the format:

For "conversation":
  Questions 1–6: Completion (fill the blank with 1–2 words or a number)
  Questions 7–10: Multiple Choice (3 options: A, B, C)

For "monologue":
  Questions 1–5: Multiple Choice (3 options: A, B, C)
  Questions 6–10: Completion (fill the blank with 1–2 words or a number)

For "discussion":
  Questions 1–4: Multiple Choice (3 options: A, B, C)
  Questions 5–10: Completion (fill the blank with 1–2 words or a number)

For "lecture":
  Questions 1–5: Completion (fill the blank with 1–2 words or a number)
  Questions 6–10: Multiple Choice (3 options: A, B, C)

Rules for ALL questions:
- Questions follow the ORDER of information in the transcript
- Answers are spread evenly — not all from the first or last paragraph

Rules for Completion:
- Answer is 1–2 words OR a number/date heard EXACTLY in the transcript
- The question text paraphrases the context but the answer is verbatim
- Use "___" for the blank

Rules for Multiple Choice:
- 3 options (A, B, C) — one correct, two plausible distractors
- Distractors may use words from the transcript but in wrong context
- No trick questions

--------------------------------------------------

OUTPUT FORMAT (STRICT JSON ONLY):

{{
  "meta": {{
    "module": "IELTS Listening",
    "format": "conversation" or "monologue" or "discussion" or "lecture",
    "target_band": 6.5,
    "word_count": integer,
    "topic": "short scenario label",
    "speakers": ["Speaker1Name", "Speaker2Name"] or ["SpeakerName"]
  }},
  "transcript": "Full transcript with speaker labels.\\nSarah: Hi, I would like to...\\nReceptionist: Of course, let me...",
  "questions": {{
    "completion": [
      {{"question_number": 1, "text": "The guest surname is ___.", "answer": "Henderson"}},
      {{"question_number": 2, "text": "Check-in date: ___ of March.", "answer": "14th"}}
    ],
    "multiple_choice": [
      {{
        "question_number": 7,
        "question": "Why does the guest prefer the ground floor?",
        "options": {{"A": "It is cheaper", "B": "She has heavy luggage", "C": "She is afraid of heights"}},
        "answer": "B"
      }}
    ]
  }}
}}

DO NOT include explanations, rationales, or extra commentary.
Return JSON only.'''

LISTENING_VALIDATION_PROMPT = '''Evaluate this IELTS Listening practice for:
1. Every completion answer appears VERBATIM in the transcript
2. Questions follow the order of information in the transcript
3. MCQ has exactly one correct answer and two plausible distractors
4. Answer distribution is spread across the transcript (not clustered)
5. Schema compliance (question_number, text/question, answer fields)

Return JSON only:
{{
  "valid": boolean,
  "issues": ["issue1", "issue2"],
  "estimated_band": number
}}'''


class ListeningGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"

    def generate(self, topic_hint: str = "") -> dict | None:
        """Generate a listening exercise with validation, then synthesize audio."""
        date = datetime.now().strftime("%Y-%m-%d")
        seed = random.randint(1000, 9999)

        result = self._generate(date, seed, topic_hint)
        if not result:
            return None

        validation = self._validate(result)
        attempts = 0
        while not validation.get("valid", False) and attempts < 3:
            attempts += 1
            result = self._generate(date, seed + attempts * 100, topic_hint)
            if result:
                validation = self._validate(result)

        if not result:
            return None

        # Synthesize audio from transcript
        try:
            audio_url = self._synthesize_audio(result)
            result["meta"]["audio_url"] = audio_url
        except Exception as e:
            print(f"TTS synthesis error: {e}")
            return None

        return result

    def _generate(self, date: str, seed: int, topic_hint: str) -> dict | None:
        prompt = LISTENING_PROMPT.format(
            date=date,
            seed=seed,
            topic_hint=topic_hint or "none — choose freely",
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS test writer. Generate valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=4000,
            )
            content = response.choices[0].message.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return None
        except Exception as e:
            print(f"Listening generation error: {e}")
            return None

    def _validate(self, practice: dict) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS test validator. Return valid JSON only."},
                    {"role": "user", "content": f"{LISTENING_VALIDATION_PROMPT}\n\nPractice to evaluate:\n{json.dumps(practice)}"},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            content = response.choices[0].message.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return {"valid": False, "issues": ["Failed to parse validation response"]}
        except Exception as e:
            print(f"Listening validation error: {e}")
            return {"valid": False, "issues": [str(e)]}

    def _synthesize_audio(self, practice: dict) -> str:
        """Convert transcript to MP3 — dialogue for multi-speaker, single voice for monologue."""
        transcript = practice.get("transcript", "")
        speakers = practice.get("meta", {}).get("speakers", [])
        fmt = practice.get("meta", {}).get("format", "monologue")

        if fmt in ("conversation", "discussion") and len(speakers) >= 2:
            voice_pair = random.choice(VOICE_PAIRS)
            return synthesize_dialogue(transcript, speakers, voice_pair)
        else:
            # Single speaker — pick a random solo voice
            solo_voices = list(VOICES.keys())
            voice_key = random.choice(solo_voices)
            # Strip speaker labels for cleaner TTS
            clean = "\n".join(
                line.split(":", 1)[1].strip() if ":" in line else line
                for line in transcript.strip().split("\n")
                if line.strip()
            )
            return synthesize(clean, voice_key)


listening_generator = ListeningGenerator()
