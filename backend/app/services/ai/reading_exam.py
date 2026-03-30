"""Reading Exam Orchestrator.

Generates a full IELTS-style reading exam: 3 sections with progressive difficulty.
Calls the existing practice_generator 3 times with different difficulty profiles.
"""
import json
import logging
from datetime import datetime

from app.services.ai.practice_generator import PracticeGenerator
from app.services.ai.reading_config import generate_metadata

logger = logging.getLogger(__name__)

# Section difficulty presets
SECTION_PROFILES = [
    {
        "section_number": 1,
        "text_complexity": 2,
        "inference_demand": 1,
        "question_difficulty": 2,
        "topic_style": "factual, descriptive",
        "target_questions": 10,
    },
    {
        "section_number": 2,
        "text_complexity": 3,
        "inference_demand": 3,
        "question_difficulty": 3,
        "topic_style": "analytical, comparative",
        "target_questions": 10,
    },
    {
        "section_number": 3,
        "text_complexity": 4,
        "inference_demand": 4,
        "question_difficulty": 4,
        "topic_style": "abstract, argumentative",
        "target_questions": 10,
    },
]


def generate_reading_exam(avoid_topics: list[str] | None = None) -> dict | None:
    """Generate a full reading exam with 3 sections.

    Returns the complete exam content dict, or None if generation fails.
    """
    generator = PracticeGenerator()
    used_topics = list(avoid_topics or [])
    sections = []

    for profile in SECTION_PROFILES:
        section = _generate_section(generator, profile, used_topics)
        if not section:
            logger.error(f"[ReadingExam] Failed to generate section {profile['section_number']}")
            return None
        sections.append(section)
        # Track used topic to avoid repetition
        topic = section.get("meta", {}).get("topic", "")
        if topic:
            used_topics.append(topic)

    # Validate the assembled exam
    if not _validate_exam(sections):
        logger.error("[ReadingExam] Validation failed")
        return None

    # Assemble
    topics_str = ", ".join(s["meta"]["topic"] for s in sections)
    total_q = sum(s["question_count"] for s in sections)

    return {
        "meta": {
            "module": "reading_full_test",
            "topic": f"Full Reading Test — {topics_str}",
            "total_questions": total_q,
            "time_limit_minutes": 60,
            "version": "v1",
        },
        "sections": sections,
    }


def _generate_section(generator: PracticeGenerator, profile: dict, avoid_topics: list[str]) -> dict | None:
    """Generate one exam section using the existing practice generator."""
    difficulty_profile = {
        "text_complexity": profile["text_complexity"],
        "inference_demand": profile["inference_demand"],
        "question_difficulty": profile["question_difficulty"],
    }

    for attempt in range(3):
        practice = generator.generate_practice(
            avoid_topics=avoid_topics,
            difficulty_profile=difficulty_profile,
        )
        if not practice:
            continue

        # Count questions
        groups = practice.get("questions", {}).get("groups", [])
        q_count = sum(len(g.get("answers", g.get("items", []))) for g in groups)

        return {
            "section_number": profile["section_number"],
            "difficulty_profile": difficulty_profile,
            "meta": practice.get("meta", {}),
            "passage": practice.get("passage", {}),
            "questions": practice.get("questions", {}),
            "question_count": q_count,
        }

    return None


def _validate_exam(sections: list[dict]) -> bool:
    """Lightweight validation for assembled exam."""
    if len(sections) != 3:
        return False

    # Check each section has questions
    for s in sections:
        if s.get("question_count", 0) < 5:
            logger.warning(f"[ReadingExam] Section {s['section_number']} has only {s.get('question_count')} questions")
            return False

    # Check topic diversity (no duplicate topics)
    topics = [s["meta"].get("topic", "") for s in sections]
    if len(set(topics)) < 3:
        logger.warning(f"[ReadingExam] Duplicate topics: {topics}")
        return False

    return True
