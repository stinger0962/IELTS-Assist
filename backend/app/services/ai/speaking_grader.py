"""IELTS Speaking — Grading pipeline.

Layer 1: Whisper transcription (done before this module is called)
Layer 2: Azure PA pronunciation scores (done before this module is called)
Layer 3: GPT-4o grades FC, LR, GRA from transcript + Azure scores inform Pronunciation band
"""
import json
import logging
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)

SPEAKING_SCORING_PROMPT = """You are a senior IELTS Speaking examiner with 15+ years of experience.
Grade this Part 2 (Long Turn) response using the official IELTS Speaking band descriptors.

## IELTS Speaking Band Descriptors (Bands 4-9)

### Fluency and Coherence (FC)
Band 9: Speaks fluently with only rare repetition or self-correction. Any hesitation is content-related. Develops topics fully and coherently.
Band 8: Speaks fluently with only occasional repetition or self-correction. Develops topics coherently and appropriately.
Band 7: Speaks at length without noticeable effort or loss of coherence. May demonstrate language-related hesitation at times. Uses a range of connectives and discourse markers.
Band 6: Is willing to speak at length though may lose coherence at times due to occasional repetition, self-correction or hesitation. Uses a range of connectives and discourse markers but not always appropriately.
Band 5: Usually maintains flow of speech but uses repetition, self-correction and/or slow speech to keep going. May over-use certain connectives and discourse markers. Produces simple speech fluently but more complex communication causes fluency problems.
Band 4: Cannot respond without noticeable pauses and may speak slowly with frequent repetition and self-correction. Links basic sentences but with repetitious use of simple connectives.

### Lexical Resource (LR)
Band 9: Uses vocabulary with full flexibility and precision in all topics. Uses idiomatic language naturally and accurately.
Band 8: Uses a wide vocabulary resource readily and flexibly. Uses less common and idiomatic vocabulary skilfully, with occasional inaccuracies. Uses paraphrase effectively.
Band 7: Uses vocabulary resource flexibly to discuss a variety of topics. Uses some less common and idiomatic vocabulary and shows some awareness of style and collocation, with some inappropriate choices. Uses paraphrase effectively.
Band 6: Has a wide enough vocabulary to discuss topics at length and make meaning clear in spite of inappropriacies. Generally paraphrases successfully.
Band 5: Manages to talk about familiar and unfamiliar topics but uses vocabulary with limited flexibility. Attempts to use paraphrase but with mixed success.
Band 4: Is able to talk about familiar topics but can only convey basic meaning on unfamiliar topics. Makes frequent errors in word choice.

### Grammatical Range and Accuracy (GRA)
Band 9: Uses a full range of structures naturally and appropriately. Produces consistently accurate structures apart from 'slips' characteristic of native speaker speech.
Band 8: Uses a wide range of structures flexibly. Produces a majority of error-free sentences with only very occasional inappropriacies or basic/non-systematic errors.
Band 7: Uses a range of complex structures with some flexibility. Frequently produces error-free sentences, though some grammatical mistakes persist.
Band 6: Uses a mix of simple and complex structures but with limited flexibility. May make frequent mistakes with complex structures though these rarely cause comprehension problems.
Band 5: Produces basic sentence forms with reasonable accuracy. Uses a limited range of more complex structures, but these usually contain errors.
Band 4: Produces basic sentence forms and some correct simple sentences but subordinate structures are rare. Errors are frequent and may lead to misunderstanding.

## Azure Pronunciation Data
{pronunciation_data}

## Instructions

1. Read the transcript as if listening to the student speak.
2. For FC, LR, GRA: assign a band score (whole or .5 increments, range 4.0-9.0) with evidence quotes.
3. For Pronunciation: use the Azure pronunciation_score as primary signal. Map it to IELTS band using:
   90-100 → 8-9, 75-89 → 7-7.5, 60-74 → 6-6.5, 45-59 → 5-5.5, <45 → 4-4.5.
   If Azure data is null, evaluate pronunciation from transcript intelligibility only (less reliable, note this).
4. Calculate overall_band as arithmetic mean of 4 criteria, rounded to nearest 0.5.
5. Write coaching feedback: 1-2 sentence summary, 2-3 strengths, 2-3 improvements.
6. If any criterion ≤5.0, flag it as dominant weakness in improvement #1.

## Output (strict JSON)

{{
  "examiner_result": {{
    "fluency_coherence": {{ "band": <number>, "evidence": "<quotes>" }},
    "lexical_resource": {{ "band": <number>, "evidence": "<quotes>" }},
    "grammatical_range_accuracy": {{ "band": <number>, "evidence": "<quotes>" }},
    "pronunciation": {{ "band": <number>, "evidence": "<quotes>" }},
    "overall_band": <number>
  }},
  "coaching_feedback": {{
    "summary": "<string>",
    "strengths": ["<string>", "<string>"],
    "improvements": ["<string>", "<string>"]
  }}
}}
"""


class SpeakingGrader:
    """IELTS Speaking grader using Azure PA + GPT-4o."""

    GRADER_VERSION = "1.0"

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o"

    def grade(self, transcript: str, cue_card: dict, azure_scores: dict | None = None) -> dict:
        """Grade a speaking response. Returns examiner result + coaching."""
        pronunciation_data = "No pronunciation data available (Azure PA unavailable)."
        if azure_scores:
            mispronounced = [
                w for w in azure_scores.get("words", [])
                if w.get("error_type") not in ("None", None)
            ]
            pronunciation_data = (
                f"Pronunciation score: {azure_scores['pronunciation_score']}/100\n"
                f"Accuracy: {azure_scores['accuracy_score']}/100\n"
                f"Fluency: {azure_scores['fluency_score']}/100\n"
                f"Prosody: {azure_scores['prosody_score']}/100\n"
                f"Mispronounced words: {json.dumps(mispronounced[:20])}"
            )

        system_prompt = SPEAKING_SCORING_PROMPT.format(
            pronunciation_data=pronunciation_data,
        )

        user_prompt = (
            f"## Cue Card\n"
            f"Topic: {cue_card.get('topic_line', '')}\n"
            f"Bullets: {', '.join(cue_card.get('bullets', []))}\n\n"
            f"## Student's Response (transcript)\n\n"
            f"{transcript}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        scoring = json.loads(raw)

        er = scoring.get("examiner_result", {})

        # Override pronunciation band with Azure mapping if available (no blending)
        if azure_scores and azure_scores.get("pronunciation_score") is not None:
            mapped = self._map_pronunciation_band(azure_scores["pronunciation_score"])
            if mapped is not None:
                er["pronunciation"]["band"] = mapped

        # Recalculate overall
        bands = [
            er.get("fluency_coherence", {}).get("band", 0),
            er.get("lexical_resource", {}).get("band", 0),
            er.get("grammatical_range_accuracy", {}).get("band", 0),
            er.get("pronunciation", {}).get("band", 0),
        ]
        er["overall_band"] = round(sum(bands) / 4 * 2) / 2

        # Attach Azure raw scores for frontend display
        if azure_scores:
            er["pronunciation"]["azure_scores"] = {
                "accuracy": azure_scores["accuracy_score"],
                "fluency": azure_scores["fluency_score"],
                "prosody": azure_scores["prosody_score"],
                "composite": azure_scores["pronunciation_score"],
            }

        scoring["grader_version"] = self.GRADER_VERSION
        scoring["model"] = self.model
        return scoring

    def _map_pronunciation_band(self, score: float | None) -> float | None:
        """Map Azure pronunciation_score (0-100) to IELTS band."""
        if score is None:
            return None
        if score >= 95:
            return 9.0
        elif score >= 90:
            return 8.5
        elif score >= 82:
            return 8.0
        elif score >= 75:
            return 7.5
        elif score >= 68:
            return 7.0
        elif score >= 60:
            return 6.5
        elif score >= 52:
            return 6.0
        elif score >= 45:
            return 5.5
        elif score >= 38:
            return 5.0
        elif score >= 30:
            return 4.5
        else:
            return 4.0
