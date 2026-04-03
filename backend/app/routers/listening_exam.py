"""Listening exam endpoints — submit + scoring."""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import GeneratedPractice, User, UserPractice
from app.services.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

BAND_MAP_40 = [
    (37, 8.5), (32, 7.5), (27, 7.0), (23, 6.5),
    (18, 6.0), (14, 5.5), (10, 5.0), (0, 4.0),
]


def _score_to_band(correct: int, total: int = 40) -> float:
    for threshold, band in BAND_MAP_40:
        if correct >= threshold:
            return band
    return 4.0


class ListeningExamSubmission(BaseModel):
    practice_id: int
    sections: list[dict]  # [{"section_number": 1, "answers": {"q_0_0": "TRUE", ...}}, ...]
    time_taken_seconds: int


@router.post("/submit-ai-listening-exam")
def submit_listening_exam(
    body: ListeningExamSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Score a full listening exam submission."""
    up = db.query(UserPractice).filter(
        UserPractice.user_id == current_user.id,
        UserPractice.practice_id == body.practice_id,
        UserPractice.submitted_at.is_(None),
    ).first()
    if not up:
        raise HTTPException(404, "Practice not found or already submitted")

    gp = db.query(GeneratedPractice).get(up.practice_id)
    content = json.loads(gp.content)
    exam_sections = content.get("sections", [])

    # Score each section
    section_results = []
    total_correct = 0
    total_questions = 0
    question_type_stats = {}

    for exam_section in exam_sections:
        sec_num = exam_section["section_number"]
        # Find user answers for this section
        user_section = next((s for s in body.sections if s.get("section_number") == sec_num), None)
        user_answers = user_section.get("answers", {}) if user_section else {}

        groups = exam_section.get("questions", {}).get("groups", [])
        sec_correct = 0
        sec_total = 0

        for gi, group in enumerate(groups):
            q_type = group.get("type", "unknown")
            items = group.get("items", [])
            group_answers = group.get("answers", [])

            if q_type not in question_type_stats:
                question_type_stats[q_type] = {"correct": 0, "total": 0}

            if q_type == "matching_headings":
                for ai, ans_obj in enumerate(group_answers):
                    key = f"mh_{gi}_{ans_obj.get('paragraph_number', ai)}"
                    user_ans = user_answers.get(key, "").strip().upper()
                    correct_val = str(ans_obj.get("answer", "")).strip().upper()
                    is_correct = user_ans == correct_val
                    sec_correct += 1 if is_correct else 0
                    sec_total += 1
                    question_type_stats[q_type]["total"] += 1
                    if is_correct:
                        question_type_stats[q_type]["correct"] += 1
            elif q_type == "multiple_choice":
                for qi, item in enumerate(items):
                    q_num = item.get("question_number", qi)
                    key = f"q_{gi}_{q_num}"
                    user_ans = user_answers.get(key, "").strip().upper()
                    correct_val = str(item.get("answer", "")).strip().upper()
                    is_correct = user_ans == correct_val
                    sec_correct += 1 if is_correct else 0
                    sec_total += 1
                    question_type_stats[q_type]["total"] += 1
                    if is_correct:
                        question_type_stats[q_type]["correct"] += 1
            elif q_type in ("completion", "sentence_completion", "summary_completion",
                            "form_completion", "table_completion", "note_completion"):
                # Completion-type questions: case-insensitive string comparison
                for qi, item in enumerate(items):
                    key = f"q_{gi}_{qi}"
                    user_ans = user_answers.get(key, "").strip().lower()
                    correct_val = str(item.get("answer", "")).strip().lower() if isinstance(item, dict) else str(item).strip().lower()
                    is_correct = user_ans == correct_val
                    sec_correct += 1 if is_correct else 0
                    sec_total += 1
                    question_type_stats[q_type]["total"] += 1
                    if is_correct:
                        question_type_stats[q_type]["correct"] += 1
            else:
                # T/F/NG, Y/N/NG, matching_information, short_answer, etc.
                for qi, item in enumerate(items):
                    key = f"q_{gi}_{qi}"
                    user_ans = user_answers.get(key, "").strip().lower()
                    correct_val = str(item.get("answer", "")).strip().lower() if isinstance(item, dict) else str(item).strip().lower()
                    is_correct = user_ans == correct_val
                    sec_correct += 1 if is_correct else 0
                    sec_total += 1
                    question_type_stats[q_type]["total"] += 1
                    if is_correct:
                        question_type_stats[q_type]["correct"] += 1

        total_correct += sec_correct
        total_questions += sec_total
        section_results.append({
            "section": sec_num,
            "correct": sec_correct,
            "total": sec_total,
            "accuracy": round(sec_correct / sec_total * 100, 1) if sec_total > 0 else 0,
        })

    overall_band = _score_to_band(total_correct, total_questions)

    # Question type breakdown
    qt_breakdown = [
        {"type": qt, "correct": stats["correct"], "total": stats["total"],
         "accuracy": round(stats["correct"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0}
        for qt, stats in sorted(question_type_stats.items(), key=lambda x: -x[1]["total"])
    ]

    result = {
        "overall": {"correct": total_correct, "total": total_questions, "band": overall_band},
        "sections": section_results,
        "question_types": qt_breakdown,
        "time_taken_seconds": body.time_taken_seconds,
    }

    up.submitted_at = datetime.utcnow()
    up.user_answers = json.dumps({"sections": body.sections, "result": result})
    up.score = overall_band
    up.correct_count = total_correct
    up.total_questions = total_questions
    db.commit()

    return result
