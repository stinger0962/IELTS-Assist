import json
import random
from datetime import datetime
from openai import OpenAI
from app.config import settings
from app.services.tts import synthesize_monologue, synthesize_dialogue, VOICE_PAIRS, VOICES

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
- 600–800 words total
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
- 700–900 words total
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
  Questions 1–4: Completion
  Questions 5–7: Matching (1 block, 3 stems)
  Questions 8–10: Multiple Choice

For "monologue":
  Questions 1–4: Multiple Choice
  Questions 5–7: Matching (1 block, 3 stems)
  Questions 8–10: Completion

For "discussion":
  Questions 1–3: Multiple Choice
  Questions 4–6: Matching (1 block, 3 stems)
  Questions 7–10: Completion

For "lecture":
  Questions 1–4: Completion
  Questions 5–7: Matching (1 block, 3 stems)
  Questions 8–10: Multiple Choice

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

Rules for Matching:
- One block of 3 stems + 5 labelled options (A–E)
- Each stem maps to one option; 2 options are distractors (unused)
- Options are short phrases (2–5 words) — e.g. features, categories, people, locations
- The instruction describes what students should match (e.g. "Match each facility to its location")
- Answers come from the transcript (paraphrased in stems, literal or near-literal in options)

--------------------------------------------------

OUTPUT FORMAT (STRICT JSON ONLY):

{{
  "meta": {{
    "module": "IELTS Listening",
    "format": "conversation" or "monologue" or "discussion" or "lecture",
    "target_band": 6.5,
    "word_count": integer,
    "topic": "short scenario label",
    "speakers": ["Speaker1Name (F)", "Speaker2Name (M)"] or ["SpeakerName (F)"]
  }},
  "transcript": "Full transcript with speaker labels.\\nSarah: Hi, I would like to...\\nReceptionist: Of course, let me...",
  "questions": {{
    "completion": [
      {{"question_number": 1, "text": "The guest surname is ___.", "answer": "Henderson"}},
      {{"question_number": 2, "text": "Check-in date: ___ of March.", "answer": "14th"}}
    ],
    "matching": [
      {{
        "question_number_start": 5,
        "question_number_end": 7,
        "instruction": "Match each facility to its location.",
        "stems": [
          {{"question_number": 5, "text": "Swimming pool"}},
          {{"question_number": 6, "text": "Restaurant"}},
          {{"question_number": 7, "text": "Gift shop"}}
        ],
        "options": ["A. Ground floor", "B. First floor", "C. Second floor", "D. Basement", "E. Rooftop"],
        "answers": {{"5": "D", "6": "B", "7": "A"}}
      }}
    ],
    "multiple_choice": [
      {{
        "question_number": 8,
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
4. Matching block has 3 stems, 5 options (A–E), and each answer is a valid option letter
5. Answer distribution is spread across the transcript (not clustered)
6. Schema compliance (question_number, text/question, answer fields; matching has question_number_start/end, stems, options, answers)

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

    def generate(self, topic_hint: str = "", format_hint: str = "") -> dict | None:
        """Generate a listening exercise with validation, then synthesize audio.

        format_hint: if set, forces a specific format (conversation/monologue/discussion/lecture).
        """
        date = datetime.now().strftime("%Y-%m-%d")
        seed = random.randint(1000, 9999)

        result = self._generate(date, seed, topic_hint, format_hint)
        if not result:
            return None

        validation = self._validate(result)
        attempts = 0
        while not validation.get("valid", False) and attempts < 3:
            attempts += 1
            result = self._generate(date, seed + attempts * 100, topic_hint, format_hint)
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

    def _generate(self, date: str, seed: int, topic_hint: str, format_hint: str = "") -> dict | None:
        prompt = LISTENING_PROMPT.format(
            date=date,
            seed=seed,
            topic_hint=topic_hint or "none — choose freely",
        )
        if format_hint:
            prompt = f'IMPORTANT: You MUST use format="{format_hint}" for this exercise. Do NOT choose a different format.\n\n' + prompt
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert IELTS test writer. Generate valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=5000,
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

    # Common name → gender lookup (fallback when GPT omits gender tags)
    FEMALE_NAMES = {
        "emma", "emily", "sarah", "lisa", "anna", "maria", "laura", "sophie",
        "jessica", "rachel", "claire", "kate", "lucy", "alice", "helen",
        "olivia", "hannah", "amy", "natalie", "rebecca", "julia", "megan",
        "charlotte", "victoria", "diana", "grace", "nina", "susan", "karen",
        "mary", "jennifer", "amanda", "stephanie", "nicole", "elizabeth",
        "catherine", "margaret", "patricia", "linda", "jane",
    }
    MALE_NAMES = {
        "james", "john", "david", "mark", "josh", "tom", "mike", "chris",
        "daniel", "robert", "jack", "ben", "sam", "alex", "ryan", "adam",
        "peter", "paul", "luke", "jake", "andrew", "nathan", "oliver",
        "william", "henry", "george", "edward", "matthew", "joseph",
        "richard", "charles", "thomas", "kevin", "brian", "steven", "eric",
        "patrick", "timothy", "jason", "jeffrey", "scott", "nicholas",
    }
    # Role-based names that are gender-neutral — skip inference
    ROLE_NAMES = {
        "receptionist", "agent", "advisor", "tutor", "professor", "guide",
        "instructor", "manager", "assistant", "librarian", "operator",
        "coordinator", "consultant", "clerk", "official", "host",
    }

    def _infer_gender(self, name: str) -> str | None:
        """Infer gender from name: 'F', 'M', or None if unknown."""
        low = name.lower().strip()
        if low in self.FEMALE_NAMES:
            return "F"
        if low in self.MALE_NAMES:
            return "M"
        return None

    def _synthesize_audio(self, practice: dict) -> str:
        """Convert transcript to MP3 — dialogue for multi-speaker, single voice for monologue."""
        transcript = practice.get("transcript", "")
        speakers = practice.get("meta", {}).get("speakers", [])
        fmt = practice.get("meta", {}).get("format", "monologue")

        if fmt in ("conversation", "discussion") and len(speakers) >= 2:
            voice_pair = random.choice(VOICE_PAIRS)
            # Parse gender tags like "Lisa (F)" or infer from name
            genders = []
            clean_speakers = []
            for s in speakers:
                s_stripped = s.strip()
                if s_stripped.endswith("(F)") or s_stripped.endswith("(f)"):
                    genders.append("F")
                    clean_speakers.append(s_stripped[:-3].strip())
                elif s_stripped.endswith("(M)") or s_stripped.endswith("(m)"):
                    genders.append("M")
                    clean_speakers.append(s_stripped[:-3].strip())
                else:
                    # Fallback: infer gender from common names
                    genders.append(self._infer_gender(s_stripped))
                    clean_speakers.append(s_stripped)
            # If we know both genders, ensure female voice → female speaker
            if len(genders) >= 2 and genders[0] and genders[1] and genders[0] != genders[1]:
                pair_genders = ("F" if "female" in voice_pair[0] else "M",
                                "F" if "female" in voice_pair[1] else "M")
                if genders[0] != pair_genders[0]:
                    voice_pair = (voice_pair[1], voice_pair[0])  # swap
            practice["meta"]["speakers"] = clean_speakers
            audio_url, timestamps = synthesize_dialogue(transcript, clean_speakers, voice_pair)
            practice["line_timestamps"] = timestamps
            return audio_url
        else:
            # Single speaker — pick a random solo voice
            solo_voices = list(VOICES.keys())
            voice_key = random.choice(solo_voices)
            # Strip speaker labels for cleaner TTS
            clean_lines = [
                line.split(":", 1)[1].strip() if ":" in line else line
                for line in transcript.strip().split("\n")
                if line.strip()
            ]
            clean = "\n".join(clean_lines)
            audio_url, timestamps = synthesize_monologue(clean, voice_key)
            practice["line_timestamps"] = timestamps
            return audio_url


listening_generator = ListeningGenerator()
