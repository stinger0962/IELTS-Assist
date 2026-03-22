# AI Speaking Practice Module — Design Spec

## Overview

Add conversational AI speaking practice to the IELTS-Assist app, simulating a real IELTS Speaking test across all 3 parts. Uses a hybrid architecture: OpenAI Whisper for transcription, Azure Pronunciation Assessment for phoneme-level scoring, GPT-4o for content grading, and Google Cloud TTS for the examiner voice.

Prerequisite: refactor the monolithic Practice.tsx (3,195 lines) and generate.py (1,284 lines) into modular per-skill files.

---

## Step 0: Codebase Refactoring (v0.20.0)

Zero functional changes. Pure extraction to prepare for the speaking module.

### Frontend — Split Practice.tsx

| New File | Content | Approx Lines |
|---|---|---|
| `pages/Practice.tsx` | Main page: skill list, routing, shared state, skill selection | ~600 |
| `components/practice/AIReadingView.tsx` | `AIReadingExerciseView` + reading styles | ~875 |
| `components/practice/AIListeningView.tsx` | `AIListeningExerciseView` + listening styles | ~535 |
| `components/practice/AIWritingView.tsx` | `AIWritingExerciseView` + writing styles | ~350 |
| `components/practice/AIGrammarView.tsx` | `AIGrammarExerciseView` + grammar styles | ~660 |
| `utils/completionMatch.ts` | `wordsToNumber`, `normalize`, `pluralMatch`, `editDistance`, `completionMatch` | ~90 |
| `utils/dictionary.ts` | `parseDictionaryEntry`, `POS_ABBR` | ~20 |

Each skill view component receives the same interface pattern:
- Props: exercise data, loading state, handlers (submit, back, generate-more)
- Self-contained: owns its answer state, rendering, styles
- Shared: vocab popup logic stays in Practice.tsx or extracted to `VocabPopup.tsx` if cleanly separable

### Backend — Split generate.py

| New File | Content | Approx Lines |
|---|---|---|
| `routers/generate.py` | Shared helpers (`_with_db_id`), shared endpoints (`explain-mistakes`, `translate-definition`, `extract-vocabulary`, `tts-preview`), `daily_generate()` cron | ~250 |
| `routers/reading.py` | Reading pool helpers + 3 endpoints (daily, generate-more, submit) + generate-reading | ~200 |
| `routers/listening.py` | Listening pool helpers + 3 endpoints + generate-listening | ~200 |
| `routers/writing.py` | Writing pool helpers + 3 endpoints + seed + grading topic extraction | ~250 |
| `routers/grammar.py` | Grammar pool helpers + 3 endpoints + generate-grammar | ~200 |

All skill routers use `APIRouter(prefix="/generate", tags=["generate"])` and are included in `main.py` so frontend URLs remain unchanged.

### Refactoring Rules
- Zero functional changes
- All existing backend tests pass (`python -m pytest tests/ -v`)
- Frontend build passes (`npm run build`)
- Frontend tests pass (`npm test`)
- No API URL changes
- Git: single commit for backend, single commit for frontend, or one combined

---

## Step 1: Speaking Part 2 — Long Turn MVP (v0.21.0)

### Architecture

**Services:**

| Service | Technology | Purpose |
|---|---|---|
| Transcription | OpenAI Whisper API (`whisper-1`) | Convert student audio to text |
| Pronunciation | Azure Speech SDK (Pronunciation Assessment) | Phoneme-level accuracy, fluency, prosody scores |
| Content Grading | GPT-4o (temperature=0) | Grade transcript for FC, LR, GRA; integrate pronunciation |
| Examiner Voice | Google Cloud TTS (existing) | Read cue card instructions aloud |

**New Backend Files:**

| File | Purpose |
|---|---|
| `services/ai/speaking_config.py` | 60+ Part 2 cue card topics, `generate_metadata(avoid_topics)` |
| `services/azure_speech.py` | Azure Pronunciation Assessment wrapper |
| `services/ai/speaking_grader.py` | 3-layer grading pipeline |
| `routers/speaking.py` | Pool endpoints + submit endpoint |

**Dependencies:**
- `azure-cognitiveservices-speech` added to `requirements.txt`
- `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` added to `config.py`

### Cue Card Bank (`speaking_config.py`)

60+ curated IELTS Part 2 topics across domains (people, places, events, objects, experiences, media, education, work).

Each cue card:
```python
{
    "id": "p2_exp_01",
    "topic_title": "A Book That Influenced You",
    "domain": "experiences",
    "topic_line": "Describe a book that has influenced you.",
    "bullets": [
        "what the book is",
        "when you read it",
        "what it is about",
        "and explain how it influenced you"
    ],
    "follow_up": "Is reading still popular among young people?"
}
```

Pool seeding is instant (no GPT needed) — same pattern as writing prompts.

### Content Storage (GeneratedPractice.content JSON)

```json
{
    "meta": {
        "module": "speaking_part2",
        "domain": "experiences",
        "topic": "A Book That Influenced You"
    },
    "cue_card": {
        "topic_line": "Describe a book that has influenced you.",
        "bullets": [
            "what the book is",
            "when you read it",
            "what it is about",
            "and explain how it influenced you"
        ],
        "follow_up": "Is reading still popular among young people?"
    },
    "cue_card_metadata": { "id": "p2_exp_01", "domain": "experiences" }
}
```

### Azure Pronunciation Assessment (`azure_speech.py`)

Azure PA in unscripted mode uses a **continuous recognition session** (event-driven, not a one-shot call). The wrapper abstracts this into a synchronous function.

```python
def assess_pronunciation(audio_path: str) -> dict:
    """
    Runs Azure PA in unscripted (topic/spontaneous speech) mode.

    Implementation detail: Sets up SpeechRecognizer with continuous recognition.
    - PronunciationAssessmentConfig: GradingSystem.HundredMark, Granularity.Phoneme,
      EnableMiscue=True, enable_prosody=True
    - Listens for `recognized` events, aggregates per-utterance scores
    - Stops on `session_stopped` or after 150s timeout
    - Aggregates: weighted average of per-utterance accuracy/fluency/prosody scores

    Returns:
    {
        "accuracy_score": float (0-100),
        "fluency_score": float (0-100),
        "prosody_score": float (0-100),
        "pronunciation_score": float (0-100, Azure weighted composite),
        "words": [
            {
                "word": str,
                "accuracy_score": float,
                "error_type": "None" | "Mispronunciation" | "Omission" | "Insertion"
            }
        ]
    }
    """
```

**Prerequisite:** `ffmpeg` must be installed on VPS (`apt install ffmpeg`) — `pydub` requires it for WebM/MP4 → WAV conversion. Verify during deploy.

### Error Handling Strategy

The submit pipeline chains 3 external services. Failures are handled with graceful degradation:

| Failure | Behavior |
|---|---|
| Audio too short (<5s) | Reject at endpoint, return 422. Do NOT mark card as submitted. |
| Audio corrupt / unreadable | `pydub` conversion fails → return 422, do not submit. |
| Whisper returns empty transcript | Return error to frontend ("No speech detected. Please try again."). Do not submit. |
| Azure PA fails / times out | **Proceed without pronunciation.** Set pronunciation band to `null`, add note in coaching. GPT grades FC/LR/GRA from transcript only. |
| GPT-4o fails | Return 500 error. Do not mark as submitted. User can retry. |

This follows the same pattern as writing_grader.py where the annotation layer can fail but scoring still returns.

### Grading Pipeline (`speaking_grader.py`)

Single GPT-4o call receives:
- Student's transcript (from Whisper)
- Cue card prompt
- Azure pronunciation scores (accuracy, fluency, prosody, mispronounced words list) — or null if Azure failed

Grades 4 IELTS Speaking criteria:

1. **Fluency & Coherence (FC)** — from transcript flow: logical progression, self-correction patterns, topic development, coherence. Whisper timestamps inform pause analysis.
2. **Lexical Resource (LR)** — vocabulary range, precision, idiomatic language, topic-specific terms.
3. **Grammatical Range & Accuracy (GRA)** — sentence complexity, error patterns, tense consistency.
4. **Pronunciation (P)** — primarily from Azure PA composite `pronunciation_score` (which weighs accuracy, fluency, and prosody together), mapped to IELTS bands. GPT adjusts based on intelligibility from transcript.

Pronunciation band mapping (Azure composite `pronunciation_score` → IELTS band):
- 90-100 → Band 8-9
- 75-89 → Band 7-7.5
- 60-74 → Band 6-6.5
- 45-59 → Band 5-5.5
- Below 45 → Band 4-4.5

Output format matches writing grader pattern:
```json
{
    "examiner_result": {
        "fluency_coherence": { "band": 6.5, "evidence": "..." },
        "lexical_resource": { "band": 7.0, "evidence": "..." },
        "grammatical_range_accuracy": { "band": 6.0, "evidence": "..." },
        "pronunciation": { "band": 6.5, "evidence": "...", "azure_scores": {...} },
        "overall_band": 6.5
    },
    "coaching_feedback": {
        "summary": "...",
        "strengths": ["...", "..."],
        "improvements": ["...", "..."]
    },
    "transcript": "Full transcript text...",
    "pronunciation_words": [
        { "word": "environment", "accuracy_score": 45.2, "error_type": "Mispronunciation" }
    ]
}
```

### API Endpoints

**Pool endpoints (same pattern as other skills):**
- `GET /generate/daily-speaking` — deal up to 3 active cue cards
- `POST /generate/generate-more-speaking` — pop 1 from pool

**Submit endpoint (different — handles audio upload via multipart form):**
- `POST /generate/submit-ai-speaking`
  - **Note:** Unlike other submit endpoints which use JSON `BaseModel` bodies, this uses `File(...)` and `Form(...)` from FastAPI for multipart upload.
  - Parameters: `audio: UploadFile = File(...)`, `practice_id: int = Form(...)`
  - Saves audio to `/var/www/ielts-assist/audio/speaking/`
  - Pipeline: validate → convert → Whisper → Azure PA → GPT-4o → store results
  - Returns full grading result
  - Expected latency: 5-10 seconds

**Audio upload handling:**
- Accept: `audio/webm`, `audio/mp4`, `audio/wav` (Safari iOS produces `audio/mp4`, Chrome/Firefox produce `audio/webm`)
- Convert to WAV using `pydub` (requires `ffmpeg` system binary on VPS)
- Reject if audio < 5 seconds or > 10MB
- Store in `/var/www/ielts-assist/audio/speaking/{user_id}_{practice_id}.wav`
- **Cleanup policy:** Delete audio files after grading is complete and results are stored in `user_answers`. Only keep files from the last 7 days as fallback.

### Frontend — `AISpeakingView.tsx`

**States:**
1. **Cue card display** — shows topic line + bullets + "Start" button
2. **Preparation** — 60-second countdown timer, cue card visible, no recording
3. **Recording** — 2-minute countdown, waveform visualizer, stop button
4. **Processing** — "Examiner is reviewing..." spinner (5-10s)
5. **Results** — 4 band scores, transcript, coaching feedback, pronunciation highlights

**Recording implementation:**
- `MediaRecorder API` with mime type negotiation: check `MediaRecorder.isTypeSupported('audio/webm')`, fall back to `audio/mp4` for Safari/iOS
- Max duration: 120 seconds (auto-stop)
- Visual: recording indicator (red dot + elapsed time)
- Stop: manual button or auto at 2 min
- Microphone permission: request via `navigator.mediaDevices.getUserMedia({ audio: true })`, show helpful message if denied

**Results display:**
- 4 criterion cards (same layout as writing results)
- Transcript with color-coded pronunciation words (green ≥80, yellow 60-79, red <60)
- Coaching feedback section
- "Finish" button to return to card list

---

## Step 1.1: Part 2 Polish (v0.21.x)

- Silence detection: auto-stop recording after 3s of silence using `AudioWorklet`
- Examiner voice reads cue card intro via Google TTS
- Post-submit audio playback alongside transcript
- Pronunciation word detail popup (tap red/yellow word → see phoneme breakdown)
- Mobile recording UX (permissions, fallback for unsupported browsers)

---

## Step 2: Speaking Part 1 — Interview (v0.22.0)

### Question Bank
30+ topic areas (hometown, work/study, hobbies, food, weather, etc.) × ~4 questions each.

### Conversational Flow
1. Session starts → GPT pre-generates 3 topic areas × 4 questions
2. Examiner asks Q1 via TTS → mic activates → user records → stop
3. Whisper transcribes → display transcript → examiner asks Q2 via TTS
4. Repeat for ~12 questions across 3 topics
5. At end → aggregate all transcripts → single grading call

### Key Differences from Part 2
- Multiple short recordings (15-30s each) vs one long recording
- Conversational UI (chat-like alternating bubbles) vs single cue card
- Per-turn Whisper transcription (for flow), batch Azure PA + GPT grading at end
- Examiner transition phrases between topics ("Now let's talk about...")

### Storage
```json
{
    "meta": { "module": "speaking_part1" },
    "topics": [
        {
            "area": "Hometown",
            "questions": ["Where is your hometown?", "What do you like about it?", ...]
        }
    ],
    "examiner_transitions": ["Let's move on to talk about...", ...]
}
```

---

## Step 3: Speaking Part 3 — Discussion (v0.23.0)

### Hybrid Question Generation
- Core questions pre-generated at pool time, linked to the Part 2 topic
- 1-2 adaptive follow-ups generated mid-session based on student's Part 2 transcript
- GPT reads Part 2 transcript → generates contextual follow-up questions

### Key Differences
- Longer expected answers (30-60s)
- Abstract/analytical questions ("Why do you think reading is declining?")
- Adaptive follow-ups make this the most "examiner-like" part

### Storage
```json
{
    "meta": { "module": "speaking_part3", "linked_part2_topic": "A Book That Influenced You" },
    "core_questions": [
        "Why do you think some people prefer reading physical books?",
        "How has technology changed the way people read?"
    ],
    "adaptive_prompt": "Based on the student's Part 2 response, generate 1-2 follow-up questions..."
}
```

---

## Step 4: Full Test Simulation (v0.24.0)

- **Exam mode**: Parts 1→2→3 in sequence, timed (11-14 min total), no feedback until end
- **Study mode**: part-by-part with optional per-turn feedback
- Combined report: overall band + per-part breakdown + per-criterion trends
- Session history: past speaking tests with score trends on Dashboard

---

## Step 5: Speaking Refinements (v0.24.x–v0.25.x)

- Pronunciation drill mode (repeat mispronounced words, Azure re-scores)
- Vocabulary extraction from transcript → Topics flashcards
- Progress tracking on Dashboard skill card
- Daily cron: generate 2 speaking exercises (1 Part 2 + 1 Part 1+3 set)

---

## Version Roadmap Summary

| Version | Milestone | New Infrastructure |
|---|---|---|
| **v0.20.0** | Codebase refactoring (prerequisite) | None |
| **v0.21.0** | Part 2 Long Turn MVP | Azure Speech SDK, audio upload endpoint |
| **v0.21.x** | Part 2 polish (silence detection, examiner voice, mobile) | — |
| **v0.22.0** | Part 1 Interview (conversational flow) | — |
| **v0.23.0** | Part 3 Discussion (adaptive follow-ups) | — |
| **v0.24.0** | Full test simulation (exam + study modes) | — |
| **v0.25.x** | Pronunciation drills, vocab extraction, dashboard | — |

## Cost Estimates

| Component | Cost per Full Test |
|---|---|
| Whisper (transcription) | ~$0.10 |
| Azure PA (3 batch calls) | ~$0.07 |
| GPT-4o (grading) | ~$0.05 |
| Google TTS (examiner) | ~$0.02 |
| **Total** | **~$0.24** |

## Technical Constraints

- Azure Speech SDK requires WAV format audio input — convert from WebM/MP4 using `pydub` + `ffmpeg` (`apt install ffmpeg` on VPS)
- `MediaRecorder` browser support: Chrome, Firefox, Edge, Safari 14.1+ — covers all major browsers. Safari uses `audio/mp4` not `audio/webm`.
- Azure F0 (free) tier: 5,000 assessments/month — sufficient for early usage
- Audio files: ~20MB per 2-min WAV. Cleanup policy: delete after grading complete, keep last 7 days as fallback.
- Practice.tsx vocab popup logic is shared across skills — may need to remain in parent or extract to shared component
- **CI environment:** `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` must be added to `config.py` with empty string defaults. Azure-dependent code must be mockable in tests (skip pronunciation assessment when key is empty).
- **Router prefix sharing:** All skill routers use `prefix="/generate"`. Endpoint names must remain globally unique across all routers sharing this prefix.
- **Cue card `follow_up` field:** Present in the data structure for future use in Part 3 (examiner asks it after the monologue). In the Part 2 MVP, it is stored but not used in the UI or grading flow.
- **Storage size:** Speaking grading results (transcript + word-level pronunciation) may be 50KB+ JSON in `UserPractice.user_answers` (Text column, unlimited in PostgreSQL). Store only mispronounced words in `pronunciation_words` to reduce size.
