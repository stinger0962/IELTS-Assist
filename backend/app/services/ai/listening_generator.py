import json
import random
from app.services.ai.llm import chat_json, diversity_seed, resolve_model
from app.services.tts import synthesize_monologue, synthesize_dialogue, VOICE_PAIRS, VOICES
from app.services.ai.listening_config import (
    generate_metadata, ACCENT_VOICE_PAIRS, ACCENT_SOLO_VOICES,
)

# ─── Step 2 Prompt: Generate Transcript ──────────────────────────────────────

TRANSCRIPT_PROMPT = '''You are an expert IELTS Listening test writer.

Write ONE original IELTS Listening transcript for this scenario:

Topic: {topic}
Format: {format} (IELTS Section {section})
Speakers: {speakers_desc}
Complication / twist: {complication}
Detail focus: {detail_focus}
Accent: {accent} — {accent_hints}
Key numbers to embed in the dialogue: {numbers_desc}

CRITICAL RULES:
1. The transcript MUST be completely original — do NOT copy any known IELTS material.
2. Invent all names, institutions, locations, phone numbers, dates, and prices.
3. Ensure all names, locations, and institutions are entirely fictional.
4. Randomize all numerical values. AVOID round numbers like 100, 500, 1000, 1200.
5. Use the specific numbers provided above where relevant.
6. Difficulty: Band 6.5 — moderate vocabulary, clear sentence structures, natural conversational fillers.

{format_instructions}

IMPORTANT: The transcript must contain EXACT words/phrases that will become
fill-in-the-blank answers. Key facts (names, numbers, dates, prices) must be
heard literally in the audio — spread them evenly throughout.

Return STRICT JSON only:
{{
  "transcript": "Full transcript with speaker labels.\\nSpeaker1: Hi...\\nSpeaker2: Of course...",
  "speakers": ["Speaker1Name (F)", "Speaker2Name (M)"],
  "topic": "short scenario label",
  "word_count": integer
}}

DO NOT include explanations outside the JSON.'''

# Format-specific writing instructions
FORMAT_INSTRUCTIONS = {
    "conversation": '''TRANSCRIPT FORMAT (conversation — 2 speakers, everyday situation):
- Use realistic names for the speakers (e.g. "Sarah", "Receptionist", "Tom")
- Format EVERY line as: "SpeakerName: dialogue text"
- Each line is one speaker turn — alternate speakers naturally
- 600–800 words total
- Use natural spoken English: contractions, fillers ("well", "actually", "right", "so"),
  self-corrections ("I mean"), and brief hesitations
- Spread key answer details evenly throughout the entire transcript''',

    "discussion": '''TRANSCRIPT FORMAT (discussion — 2 speakers, academic context):
- Use realistic names for the speakers (e.g. "Dr. Wilson", "Emma")
- Format EVERY line as: "SpeakerName: dialogue text"
- Each line is one speaker turn — alternate speakers naturally
- 600–800 words total
- Use academic vocabulary and reasoning language ("I think we should",
  "the data suggests", "on the other hand")
- Include natural fillers and self-corrections for realism''',

    "monologue": '''TRANSCRIPT FORMAT (monologue — 1 speaker, practical information):
- Use a single speaker name (e.g. "Guide", "Coordinator")
- Format as: "SpeakerName: text" (split into logical paragraphs)
- 700–900 words total
- Organise into 3–4 clear sections with signpost language
  ("First of all", "Moving on to", "Finally")
- Use natural spoken style, not written essay style''',

    "lecture": '''TRANSCRIPT FORMAT (lecture — 1 speaker, academic subject):
- Use a single speaker name with academic title (e.g. "Professor Chen", "Dr. Patel")
- Format as: "SpeakerName: text" (split into logical paragraphs)
- 700–900 words total
- Organise into 3–4 clear sections with signpost language
- Include academic examples, studies, data points, and research references
- Use natural spoken style with occasional asides to engage the audience''',
}

# Section number mapping
FORMAT_SECTION = {
    "conversation": 1,
    "monologue": 2,
    "discussion": 3,
    "lecture": 4,
}


# ─── Step 3 Prompt: Generate Questions ───────────────────────────────────────

QUESTIONS_PROMPT = '''You are an expert IELTS Listening question writer.

Given the transcript below, generate exactly 10 questions.

QUESTION DISTRIBUTION for "{format}" format:
{question_distribution}

Completion subtype for this exercise: "{completion_subtype}"
{completion_subtype_instructions}

Rules for Completion:
- Answer is 1–2 words OR a number/date heard EXACTLY in the transcript
- The question text paraphrases the context but the answer is verbatim
- Use "___" for the blank
- Each completion question MUST include: "subtype": "{completion_subtype}" and "group_title": "{completion_group_title}"

Rules for Multiple Choice:
- 3 options (A, B, C) — one correct, two plausible distractors
- Distractors may use words from the transcript but in wrong context
- No trick questions

Rules for Matching:
- One block of 3 stems + 5 labelled options (A–E)
- Each stem maps to one option; 2 options are distractors (unused)
- Options are short phrases (2–5 words)
- The instruction describes what students should match
- Answers come from the transcript (paraphrased in stems, literal or near-literal in options)

Rules for ALL questions:
- Questions follow the ORDER of information in the transcript
- Answers are spread evenly — not all from the first or last paragraph

TRANSCRIPT:
{transcript}

Return STRICT JSON only:
{{
  "questions": {{
    "completion": [
      {{"question_number": 1, "text": "The guest surname is ___.", "answer": "Henderson", "subtype": "{completion_subtype}", "group_title": "{completion_group_title}"}}
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

DO NOT include explanations outside the JSON.'''

# Question distribution per format
QUESTION_DISTRIBUTIONS = {
    "conversation": """Questions 1–4: Completion (fill the blank with 1–2 words or a number)
Questions 5–7: Matching (1 block, 3 stems, 5 options A–E)
Questions 8–10: Multiple Choice (3 options: A, B, C)""",

    "monologue": """Questions 1–4: Multiple Choice (3 options: A, B, C)
Questions 5–7: Matching (1 block, 3 stems, 5 options A–E)
Questions 8–10: Completion (fill the blank with 1–2 words or a number)""",

    "discussion": """Questions 1–3: Multiple Choice (3 options: A, B, C)
Questions 4–6: Matching (1 block, 3 stems, 5 options A–E)
Questions 7–10: Completion (fill the blank with 1–2 words or a number)""",

    "lecture": """Questions 1–4: Completion (fill the blank with 1–2 words or a number)
Questions 5–7: Matching (1 block, 3 stems, 5 options A–E)
Questions 8–10: Multiple Choice (3 options: A, B, C)""",
}

# Completion subtype weights by format
COMPLETION_SUBTYPE_WEIGHTS = {
    "conversation": [("form", 50), ("sentence", 50)],
    "monologue": [("note", 40), ("summary", 30), ("sentence", 30)],
    "discussion": [("summary", 50), ("sentence", 50)],
    "lecture": [("note", 40), ("table", 30), ("summary", 30)],
}

COMPLETION_SUBTYPE_INSTRUCTIONS = {
    "form": 'Format completion questions as form fields. The "text" should look like a labelled form field, e.g. "Surname: ___", "Check-in date: ___", "Room type: ___". The group_title should be a form name like "BOOKING FORM" or "REGISTRATION FORM".',
    "table": 'Format completion questions as table cells. The "text" should reference a row/column context, e.g. "Morning session: ___", "Building A — capacity: ___". The group_title should be a table heading like "SCHEDULE" or "FACILITY DETAILS".',
    "note": 'Format completion questions as bullet-point notes. The "text" should look like note entries, e.g. "• Main topic: ___", "• Recommended by: ___". The group_title should be a note heading like "LECTURE NOTES" or "MEETING NOTES".',
    "summary": 'Format completion questions as sentences in a summary paragraph. The "text" should be a flowing sentence with a blank, e.g. "The researcher found that ___ was the main factor." The group_title should be "SUMMARY".',
    "sentence": 'Format completion questions as standalone sentences with blanks. The "text" should be a complete sentence, e.g. "The total cost is ___ per month." No group_title needed.',
}

COMPLETION_SUBTYPE_GROUP_TITLES = {
    "form": ["BOOKING FORM", "REGISTRATION FORM", "APPLICATION FORM", "ENQUIRY FORM", "MEMBERSHIP FORM", "ORDER FORM"],
    "table": ["SCHEDULE", "FACILITY DETAILS", "COURSE INFORMATION", "COMPARISON TABLE", "PRICE LIST"],
    "note": ["LECTURE NOTES", "MEETING NOTES", "RESEARCH NOTES", "TOUR INFORMATION", "BRIEFING NOTES"],
    "summary": ["SUMMARY"],
    "sentence": [""],
}


def _pick_completion_subtype(fmt: str) -> tuple[str, str]:
    """Pick a completion subtype and group_title based on format weights."""
    weights = COMPLETION_SUBTYPE_WEIGHTS.get(fmt, [("sentence", 100)])
    subtypes, wts = zip(*weights)
    subtype = random.choices(subtypes, weights=wts, k=1)[0]
    titles = COMPLETION_SUBTYPE_GROUP_TITLES.get(subtype, [""])
    group_title = random.choice(titles)
    return subtype, group_title


# ─── Validation Prompt ───────────────────────────────────────────────────────

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
        self.model = resolve_model("generator")

    def generate(self, topic_hint: str = "", format_hint: str = "") -> dict | None:
        """Generate a listening exercise via 3-step pipeline, then synthesize audio.

        Steps:
        1. generate_metadata() — pure Python randomization (instant, free)
        2. _generate_transcript(metadata) — GPT call #1
        3. _generate_questions(metadata, transcript) — GPT call #2
        Then: _validate() + _synthesize_audio()

        topic_hint: comma-separated list of recently used topics to avoid.
        format_hint: if set, forces a specific format.
        """
        # Parse avoid topics from hint string
        avoid_topics = []
        if topic_hint:
            raw = topic_hint.replace("avoid:", "").strip()
            avoid_topics = [t.strip() for t in raw.split(",") if t.strip()]

        # Step 1: Metadata (pure Python — instant)
        metadata = generate_metadata(avoid_topics=avoid_topics, format_hint=format_hint)

        # Step 2: Transcript (GPT call #1)
        transcript_data = self._generate_transcript(metadata)
        if not transcript_data:
            return None

        # Step 3: Questions (GPT call #2)
        result = self._generate_questions(metadata, transcript_data)
        if not result:
            return None

        # Validate
        validation = self._validate(result)
        attempts = 0
        while not validation.get("valid", False) and attempts < 3:
            attempts += 1
            # Regenerate with fresh metadata
            metadata = generate_metadata(avoid_topics=avoid_topics, format_hint=format_hint)
            transcript_data = self._generate_transcript(metadata)
            if transcript_data:
                result = self._generate_questions(metadata, transcript_data)
                if result:
                    validation = self._validate(result)

        if not result:
            return None

        # Store accent in meta for TTS voice selection
        result["meta"]["accent"] = metadata.get("accent", "")

        # Synthesize audio from transcript
        try:
            audio_url = self._synthesize_audio(result)
            result["meta"]["audio_url"] = audio_url
        except Exception as e:
            print(f"TTS synthesis error: {e}")
            return None

        return result

    def _generate_transcript(self, metadata: dict) -> dict | None:
        """Step 2: Generate transcript via GPT. Returns {transcript, speakers, topic, word_count}."""
        fmt = metadata["format"]

        # Build speakers description
        roles = metadata["speaker_roles"]
        if len(roles) == 2:
            speakers_desc = f"{roles[0]} and {roles[1]} (assign realistic names with gender tags like 'Sarah (F)', 'Tom (M)')"
        else:
            speakers_desc = f"{roles[0]} (assign a realistic name with gender tag)"

        # Build numbers description
        nums = metadata["numbers"]
        if nums:
            numbers_desc = ", ".join(f"{k.replace('_', ' ')} = {v}" for k, v in nums.items())
        else:
            numbers_desc = "Generate realistic numbers — avoid round values like 100, 500, 1000"

        prompt = TRANSCRIPT_PROMPT.format(
            topic=metadata["topic"],
            format=fmt,
            section=FORMAT_SECTION.get(fmt, 1),
            speakers_desc=speakers_desc,
            complication=metadata["complication"],
            detail_focus=metadata["detail_focus"],
            accent=metadata["accent"],
            accent_hints=metadata["accent_hints"],
            numbers_desc=numbers_desc,
            format_instructions=FORMAT_INSTRUCTIONS.get(fmt, ""),
        )

        try:
            content = chat_json(
                tier="generator",
                # diversity_seed replaces the variety temperature=0.85 used to give us
                messages=[
                    {"role": "system", "content": "You are an expert IELTS test writer. Generate valid JSON only.\n\n" + diversity_seed()},
                    {"role": "user", "content": prompt},
                ],
                max_output_tokens=3500,
                temperature=0.85,
                reasoning_effort="low",
            )
            return self._parse_json(content)
        except Exception as e:
            print(f"Transcript generation error: {e}")
            return None

    def _generate_questions(self, metadata: dict, transcript_data: dict) -> dict | None:
        """Step 3: Generate questions based on transcript. Returns full practice dict."""
        fmt = metadata["format"]
        transcript = transcript_data.get("transcript", "")

        # Pick completion subtype
        completion_subtype, completion_group_title = _pick_completion_subtype(fmt)

        prompt = QUESTIONS_PROMPT.format(
            format=fmt,
            question_distribution=QUESTION_DISTRIBUTIONS.get(fmt, QUESTION_DISTRIBUTIONS["conversation"]),
            transcript=transcript,
            completion_subtype=completion_subtype,
            completion_group_title=completion_group_title,
            completion_subtype_instructions=COMPLETION_SUBTYPE_INSTRUCTIONS.get(completion_subtype, ""),
        )

        try:
            content = chat_json(
                tier="generator",
                messages=[
                    {"role": "system", "content": "You are an expert IELTS test question writer. Generate valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                max_output_tokens=2500,
                temperature=0.5,
                reasoning_effort="medium",
            )
            questions_data = self._parse_json(content)
            if not questions_data:
                return None

            # Assemble final practice dict
            questions = questions_data.get("questions", questions_data)
            return {
                "meta": {
                    "module": "IELTS Listening",
                    "format": fmt,
                    "target_band": 6.5,
                    "word_count": transcript_data.get("word_count", 0),
                    "topic": transcript_data.get("topic", metadata["topic"]),
                    "speakers": transcript_data.get("speakers", []),
                },
                "transcript": transcript,
                "questions": {
                    "completion": questions.get("completion", []),
                    "multiple_choice": questions.get("multiple_choice", []),
                    "matching": questions.get("matching", []),
                },
            }
        except Exception as e:
            print(f"Question generation error: {e}")
            return None

    def _parse_json(self, content: str) -> dict | None:
        """Extract JSON from GPT response text."""
        try:
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return None
        except (json.JSONDecodeError, Exception):
            return None

    def _validate(self, practice: dict) -> dict:
        try:
            content = chat_json(
                tier="generator",
                messages=[
                    {"role": "system", "content": "You are an expert IELTS test validator. Return valid JSON only."},
                    {"role": "user", "content": f"{LISTENING_VALIDATION_PROMPT}\n\nPractice to evaluate:\n{json.dumps(practice)}"},
                ],
                max_output_tokens=500,
                temperature=0.3,
                reasoning_effort="low",
            )
            return self._parse_json(content) or {"valid": False, "issues": ["Failed to parse validation response"]}
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
        accent = practice.get("meta", {}).get("accent", "")

        if fmt in ("conversation", "discussion") and len(speakers) >= 2:
            # Use accent-matched voice pair if available, else random
            if accent and accent in ACCENT_VOICE_PAIRS:
                voice_pair = ACCENT_VOICE_PAIRS[accent]
            else:
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
            # Single speaker — use accent-matched voice or random
            if accent and accent in ACCENT_SOLO_VOICES:
                voice_key = random.choice(ACCENT_SOLO_VOICES[accent])
            else:
                voice_key = random.choice(list(VOICES.keys()))
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
