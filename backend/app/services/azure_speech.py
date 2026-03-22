"""Azure Pronunciation Assessment wrapper.

Uses continuous recognition in unscripted (spontaneous speech) mode.
Returns phoneme-level accuracy, fluency, prosody scores.
Gracefully returns None if AZURE_SPEECH_KEY is not configured.
"""
import logging
import threading
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def assess_pronunciation(audio_path: str) -> dict | None:
    """
    Run Azure PA on a WAV file. Returns scores dict or None if unavailable.

    Uses continuous recognition with PronunciationAssessmentConfig in
    unscripted mode. Aggregates per-utterance scores across the full audio.
    """
    if not settings.AZURE_SPEECH_KEY:
        logger.warning("AZURE_SPEECH_KEY not set — skipping pronunciation assessment")
        return None

    if not Path(audio_path).exists():
        logger.error(f"Audio file not found: {audio_path}")
        return None

    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        logger.error("azure-cognitiveservices-speech not installed")
        return None

    speech_config = speechsdk.SpeechConfig(
        subscription=settings.AZURE_SPEECH_KEY,
        region=settings.AZURE_SPEECH_REGION,
    )
    audio_config = speechsdk.audio.AudioConfig(filename=audio_path)

    # Configure pronunciation assessment — unscripted, phoneme-level
    pa_config = speechsdk.PronunciationAssessmentConfig(
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=True,
    )
    pa_config.enable_prosody_assessment()

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
        language="en-US",
    )
    pa_config.apply_to(recognizer)

    # Collect results from continuous recognition
    all_words = []
    utterance_scores = []
    done_event = threading.Event()

    def on_recognized(evt):
        result = evt.result
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            pa_result = speechsdk.PronunciationAssessmentResult(result)
            utterance_scores.append({
                "accuracy": pa_result.accuracy_score,
                "fluency": pa_result.fluency_score,
                "prosody": pa_result.prosody_score if hasattr(pa_result, 'prosody_score') else 0,
                "pronunciation": pa_result.pronunciation_score,
            })
            if hasattr(pa_result, 'words') and pa_result.words:
                for word in pa_result.words:
                    error_type = "None"
                    if hasattr(word, 'error_type'):
                        error_type = word.error_type.name if hasattr(word.error_type, 'name') else str(word.error_type)
                    all_words.append({
                        "word": word.word,
                        "accuracy_score": word.accuracy_score,
                        "error_type": error_type,
                    })

    def on_canceled(evt):
        done_event.set()

    def on_session_stopped(evt):
        done_event.set()

    recognizer.recognized.connect(on_recognized)
    recognizer.canceled.connect(on_canceled)
    recognizer.session_stopped.connect(on_session_stopped)

    recognizer.start_continuous_recognition()
    done_event.wait(timeout=150)  # 150s max for a 2-min recording
    recognizer.stop_continuous_recognition()

    if not utterance_scores:
        logger.warning("Azure PA returned no utterance scores")
        return None

    # Aggregate scores across utterances (simple average)
    n = len(utterance_scores)
    avg = lambda key: sum(u[key] for u in utterance_scores) / n

    return {
        "accuracy_score": round(avg("accuracy"), 1),
        "fluency_score": round(avg("fluency"), 1),
        "prosody_score": round(avg("prosody"), 1),
        "pronunciation_score": round(avg("pronunciation"), 1),
        "words": all_words,
    }
