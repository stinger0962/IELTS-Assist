"""Listening Exam Orchestrator.

Generates a full IELTS-style listening exam: 4 sections with progressive difficulty.
Calls the existing ListeningGenerator 4 times with different format hints.
"""
import json
import logging

from app.services.ai.listening_generator import ListeningGenerator

logger = logging.getLogger(__name__)

SECTION_PROFILES = [
    {
        "section_number": 1,
        "format_hint": "conversation",
        "category_hint": "daily_life",
        "description": "Two speakers in a daily/social context",
    },
    {
        "section_number": 2,
        "format_hint": "monologue",
        "category_hint": "public_info",
        "description": "Monologue on a social/everyday topic",
    },
    {
        "section_number": 3,
        "format_hint": "discussion",
        "category_hint": "academic",
        "description": "Discussion in an educational/training context",
    },
    {
        "section_number": 4,
        "format_hint": "lecture",
        "category_hint": "academic",
        "description": "Academic lecture or monologue",
    },
]


def generate_listening_exam(avoid_topics: list[str] | None = None) -> dict | None:
    """Generate a full listening exam with 4 sections.

    Returns the complete exam content dict, or None if generation fails.
    """
    generator = ListeningGenerator()
    used_topics = list(avoid_topics or [])
    sections = []

    for profile in SECTION_PROFILES:
        section = _generate_section(generator, profile, used_topics)
        if not section:
            logger.error(f"[ListeningExam] Failed to generate section {profile['section_number']}")
            return None
        sections.append(section)
        topic = section.get("meta", {}).get("topic", "")
        if topic:
            used_topics.append(topic)

    if not _validate_exam(sections):
        logger.error("[ListeningExam] Validation failed")
        return None

    topics_str = ", ".join(s["meta"]["topic"] for s in sections)
    total_q = sum(s["question_count"] for s in sections)

    return {
        "meta": {
            "module": "listening_full_test",
            "topic": f"Full Listening Test — {topics_str}",
            "total_questions": total_q,
            "time_limit_minutes": 30,
            "version": "v1",
        },
        "sections": sections,
    }


def _generate_section(generator: ListeningGenerator, profile: dict, avoid_topics: list[str]) -> dict | None:
    """Generate one exam section using the existing listening generator."""
    topic_hint = "avoid:" + ",".join(avoid_topics) if avoid_topics else ""

    for attempt in range(3):
        practice = generator.generate(
            topic_hint=topic_hint,
            format_hint=profile["format_hint"],
        )
        if not practice:
            continue

        # Count questions — listening uses flat format: {completion: [], multiple_choice: [], matching: []}
        questions = practice.get("questions", {})
        if isinstance(questions, list):
            q_count = len(questions)
        elif questions.get("groups"):
            q_count = sum(len(g.get("items", [])) for g in questions["groups"])
        else:
            # Flat listening format
            q_count = (
                len(questions.get("completion", []))
                + len(questions.get("multiple_choice", []))
                + len(questions.get("matching", []))
            )

        return {
            "section_number": profile["section_number"],
            "format": profile["format_hint"],
            "description": profile["description"],
            "meta": practice.get("meta", {}),
            "audio_url": practice.get("meta", {}).get("audio_url", ""),
            "transcript": practice.get("transcript", ""),
            "questions": practice.get("questions", {}),
            "question_count": q_count,
        }

    return None


def _validate_exam(sections: list[dict]) -> bool:
    """Lightweight validation for assembled exam."""
    if len(sections) != 4:
        return False
    for s in sections:
        if s.get("question_count", 0) < 5:
            logger.warning(f"[ListeningExam] Section {s['section_number']} has only {s.get('question_count')} questions")
            return False
        if not s.get("audio_url"):
            logger.warning(f"[ListeningExam] Section {s['section_number']} missing audio")
            return False
    topics = [s["meta"].get("topic", "") for s in sections]
    if len(set(topics)) < 4:
        logger.warning(f"[ListeningExam] Duplicate topics: {topics}")
        return False
    return True
