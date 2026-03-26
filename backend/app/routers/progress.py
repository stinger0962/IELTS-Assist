import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta
from app.database import get_db
from app.models.models import User, UserProgress, UserPractice, GeneratedPractice, StudySession, SkillType

logger = logging.getLogger(__name__)
from app.schemas.schemas import (
    UserProgressResponse, ProgressStats, UserProgressUpdate,
    StudySessionCreate, StudySessionResponse
)
from app.services.auth import get_current_user

router = APIRouter()

@router.get("/progress", response_model=List[UserProgressResponse])
def get_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(UserProgress).filter(UserProgress.user_id == current_user.id).all()

@router.post("/progress", response_model=UserProgressResponse)
def update_progress(
    progress_update: UserProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    progress = db.query(UserProgress).filter(
        UserProgress.user_id == current_user.id,
        UserProgress.skill == progress_update.skill
    ).first()
    
    if not progress:
        progress = UserProgress(
            user_id=current_user.id,
            skill=progress_update.skill,
            band_score=progress_update.band_score or 0,
            total_exercises=progress_update.total_questions or 0,
            correct_answers=progress_update.correct_answers or 0,
            study_time_minutes=progress_update.study_time_minutes or 0
        )
        db.add(progress)
    else:
        if progress_update.band_score is not None:
            progress.band_score = progress_update.band_score
        if progress_update.total_questions is not None:
            progress.total_exercises += progress_update.total_questions
        if progress_update.correct_answers is not None:
            progress.correct_answers += progress_update.correct_answers
        if progress_update.study_time_minutes is not None:
            progress.study_time_minutes += progress_update.study_time_minutes
        progress.last_practiced = datetime.utcnow()
    
    db.commit()
    db.refresh(progress)
    return progress

@router.get("/progress/stats", response_model=ProgressStats)
def get_progress_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    progress_list = db.query(UserProgress).filter(
        UserProgress.user_id == current_user.id
    ).all()
    
    total_time = sum(p.study_time_minutes for p in progress_list)
    total_exercises = sum(p.total_exercises for p in progress_list)
    band_scores = [p.band_score for p in progress_list if p.band_score > 0]
    avg_band = sum(band_scores) / len(band_scores) if band_scores else 0.0
    
    # Calculate streak
    sessions = db.query(StudySession).filter(
        StudySession.user_id == current_user.id,
        StudySession.completed == True
    ).order_by(StudySession.created_at.desc()).all()
    
    streak_days = 0
    if sessions:
        today = datetime.utcnow().date()
        current_date = today
        session_dates = {s.created_at.date() for s in sessions}
        
        while current_date in session_dates:
            streak_days += 1
            current_date -= timedelta(days=1)
    
    return ProgressStats(
        total_study_time=total_time,
        total_exercises=total_exercises,
        average_band=round(avg_band, 1),
        streak_days=streak_days,
        progress=progress_list
    )

@router.post("/sessions", response_model=StudySessionResponse)
def create_session(
    session: StudySessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_session = StudySession(
        user_id=current_user.id,
        skill=session.skill,
        duration_minutes=session.duration_minutes,
        notes=session.notes
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

@router.get("/sessions", response_model=List[StudySessionResponse])
def get_sessions(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(StudySession).filter(
        StudySession.user_id == current_user.id
    ).order_by(StudySession.created_at.desc()).limit(limit).all()


# ── Speaking insights ────────────────────────────────────────────────────────

CRITERION_KEYS = [
    ("fluency_coherence", "Fluency & Coherence"),
    ("lexical_resource", "Lexical Resource"),
    ("grammatical_range_accuracy", "Grammar Range & Accuracy"),
    ("pronunciation", "Pronunciation"),
]

WEAKNESS_RECOMMENDATIONS = {
    "fluency_coherence": "Practice speaking at length without pauses. Use discourse markers naturally.",
    "lexical_resource": "Build topic-specific vocabulary. Use paraphrase instead of repetition.",
    "grammatical_range_accuracy": "Focus on complex sentence structures. Reduce recurring grammar errors.",
    "pronunciation": "Practice mispronounced words. Use the pronunciation analysis for targeted feedback.",
}


@router.get("/progress/speaking-insights")
def get_speaking_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate speaking criterion data across all submitted sessions."""
    rows = (
        db.query(UserPractice, GeneratedPractice)
        .join(GeneratedPractice, UserPractice.practice_id == GeneratedPractice.id)
        .filter(
            UserPractice.user_id == current_user.id,
            GeneratedPractice.skill == "speaking",
            UserPractice.submitted_at.isnot(None),
        )
        .order_by(UserPractice.submitted_at.desc())
        .all()
    )

    # Parse criterion bands from each session
    sessions = []
    for up, gp in rows:
        try:
            data = json.loads(up.user_answers) if up.user_answers else {}
            er = data.get("examiner_result", {})
            bands = {}
            for key, _ in CRITERION_KEYS:
                b = er.get(key, {}).get("band")
                if b is not None:
                    bands[key] = float(b)
            if bands and er.get("overall_band") is not None:
                sessions.append({
                    "bands": bands,
                    "overall": float(er["overall_band"]),
                    "date": up.submitted_at.isoformat() if up.submitted_at else None,
                    "topic": gp.topic,
                })
        except Exception:
            continue

    total = len(sessions)
    if total == 0:
        return {
            "total_sessions": 0,
            "criteria": [],
            "weakest_criterion": None,
            "weakest_recommendation": None,
            "best_session_band": None,
            "worst_session_band": None,
            "overall_average": None,
            "recent_sessions": [],
        }

    # Per-criterion averages
    criteria = []
    weakest_key = None
    weakest_avg = 10.0
    for key, label in CRITERION_KEYS:
        all_bands = [s["bands"][key] for s in sessions if key in s["bands"]]
        if not all_bands:
            criteria.append({"name": key, "label": label, "average": 0, "trend": "insufficient"})
            continue

        avg = round(sum(all_bands) / len(all_bands) * 2) / 2  # nearest 0.5

        # Trend: last 3 vs previous 3
        if total >= 6:
            recent_3 = [s["bands"][key] for s in sessions[:3] if key in s["bands"]]
            prev_3 = [s["bands"][key] for s in sessions[3:6] if key in s["bands"]]
            if recent_3 and prev_3:
                delta = (sum(recent_3) / len(recent_3)) - (sum(prev_3) / len(prev_3))
                trend = "improving" if delta > 0.25 else "declining" if delta < -0.25 else "stable"
            else:
                trend = "insufficient"
        else:
            trend = "insufficient"

        criteria.append({"name": key, "label": label, "average": avg, "trend": trend})

        if avg < weakest_avg:
            weakest_avg = avg
            weakest_key = key

    # Overall stats
    overall_bands = [s["overall"] for s in sessions]
    overall_avg = round(sum(overall_bands) / len(overall_bands) * 2) / 2

    # Recent sessions (last 5)
    recent = [
        {"date": s["date"], "overall_band": s["overall"], "topic": s["topic"]}
        for s in sessions[:5]
    ]

    weakest_label = None
    for key, label in CRITERION_KEYS:
        if key == weakest_key:
            weakest_label = label
            break

    return {
        "total_sessions": total,
        "criteria": criteria,
        "weakest_criterion": weakest_label,
        "weakest_recommendation": WEAKNESS_RECOMMENDATIONS.get(weakest_key) if weakest_key else None,
        "best_session_band": max(overall_bands),
        "worst_session_band": min(overall_bands),
        "overall_average": overall_avg,
        "recent_sessions": recent,
    }


# ── Writing insights ─────────────────────────────────────────────────────────

WRITING_CRITERION_KEYS = [
    ("task_response", "Task Response"),
    ("coherence_cohesion", "Coherence & Cohesion"),
    ("lexical_resource", "Lexical Resource"),
    ("grammatical_range_accuracy", "Grammar Range & Accuracy"),
]

WRITING_WEAKNESS_RECOMMENDATIONS = {
    "task_response": "Address all parts of the question. Develop your position clearly with specific examples.",
    "coherence_cohesion": "Use paragraphing strategically. Improve logical flow between ideas.",
    "lexical_resource": "Build topic-specific vocabulary. Avoid repetition by using synonyms and paraphrases.",
    "grammatical_range_accuracy": "Practice complex sentence structures. Proofread for accuracy.",
}


@router.get("/progress/writing-insights")
def get_writing_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate writing criterion data across all submitted sessions."""
    rows = (
        db.query(UserPractice, GeneratedPractice)
        .join(GeneratedPractice, UserPractice.practice_id == GeneratedPractice.id)
        .filter(
            UserPractice.user_id == current_user.id,
            GeneratedPractice.skill == "writing",
            UserPractice.submitted_at.isnot(None),
        )
        .order_by(UserPractice.submitted_at.desc())
        .all()
    )

    sessions = []
    for up, gp in rows:
        try:
            data = json.loads(up.user_answers) if up.user_answers else {}
            grading = data.get("grading", {})
            er = grading.get("examiner_result", {})
            bands = {}
            for key, _ in WRITING_CRITERION_KEYS:
                b = er.get(key, {}).get("band")
                if b is not None:
                    bands[key] = float(b)
            if bands and er.get("overall_band") is not None:
                sessions.append({
                    "bands": bands,
                    "overall": float(er["overall_band"]),
                    "date": up.submitted_at.isoformat() if up.submitted_at else None,
                    "topic": gp.topic,
                })
        except Exception:
            continue

    total = len(sessions)
    if total == 0:
        return {
            "total_sessions": 0,
            "criteria": [],
            "weakest_criterion": None,
            "weakest_recommendation": None,
            "best_session_band": None,
            "worst_session_band": None,
            "overall_average": None,
            "recent_sessions": [],
        }

    criteria = []
    weakest_key = None
    weakest_avg = 10.0
    for key, label in WRITING_CRITERION_KEYS:
        all_bands = [s["bands"][key] for s in sessions if key in s["bands"]]
        if not all_bands:
            criteria.append({"name": key, "label": label, "average": 0, "trend": "insufficient"})
            continue
        avg = round(sum(all_bands) / len(all_bands) * 2) / 2
        if total >= 6:
            recent_3 = [s["bands"][key] for s in sessions[:3] if key in s["bands"]]
            prev_3 = [s["bands"][key] for s in sessions[3:6] if key in s["bands"]]
            if recent_3 and prev_3:
                delta = (sum(recent_3) / len(recent_3)) - (sum(prev_3) / len(prev_3))
                trend = "improving" if delta > 0.25 else "declining" if delta < -0.25 else "stable"
            else:
                trend = "insufficient"
        else:
            trend = "insufficient"
        criteria.append({"name": key, "label": label, "average": avg, "trend": trend})
        if avg < weakest_avg:
            weakest_avg = avg
            weakest_key = key

    overall_bands = [s["overall"] for s in sessions]
    overall_avg = round(sum(overall_bands) / len(overall_bands) * 2) / 2
    recent = [{"date": s["date"], "overall_band": s["overall"], "topic": s["topic"]} for s in sessions[:5]]

    weakest_label = None
    for key, label in WRITING_CRITERION_KEYS:
        if key == weakest_key:
            weakest_label = label
            break

    return {
        "total_sessions": total,
        "criteria": criteria,
        "weakest_criterion": weakest_label,
        "weakest_recommendation": WRITING_WEAKNESS_RECOMMENDATIONS.get(weakest_key) if weakest_key else None,
        "best_session_band": max(overall_bands),
        "worst_session_band": min(overall_bands),
        "overall_average": overall_avg,
        "recent_sessions": recent,
    }


# ── Accuracy-based insights (reading, listening, grammar) ────────────────────


def _extract_question_type_stats(user_answers_str: str, exercise_content_str: str, skill: str):
    """Parse user_answers and exercise content to build per-question-type accuracy.

    Returns dict[str, {"correct": int, "total": int}].

    user_answers is a JSON string of a flat key-value map, e.g.:
      Reading new format: {"q_0_1": "True", "q_1_3": "B", "mh_0_A": "iii"}
      Reading legacy:     {"tfng_1": "True", "mc_0": "A", "mh_1": "B"}
      Listening:          {"comp_0": "50", "mc_0": "B", "match_0_1": "C"}

    exercise_content is the GeneratedPractice.content JSON with full exercise data.
    """
    stats: dict = {}

    try:
        answers = json.loads(user_answers_str) if user_answers_str else {}
    except (json.JSONDecodeError, TypeError):
        return stats

    if not isinstance(answers, dict):
        return stats

    try:
        content = json.loads(exercise_content_str) if exercise_content_str else {}
    except (json.JSONDecodeError, TypeError):
        content = {}

    if not isinstance(content, dict):
        content = {}

    def inc(qtype: str, is_correct: bool):
        if qtype not in stats:
            stats[qtype] = {"correct": 0, "total": 0}
        stats[qtype]["total"] += 1
        if is_correct:
            stats[qtype]["correct"] += 1

    def _normalize_completion(s: str) -> str:
        """Normalize for flexible completion matching (lowercase, strip punctuation/articles)."""
        import re
        s = s.lower().strip().rstrip('.').strip()
        s = re.sub(r"^(the|a|an)\s+", "", s)
        s = re.sub(r"['\"-]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _completion_match(user: str, correct: str) -> bool:
        """Flexible matching for completion/short-answer questions."""
        if not user:
            return False
        nu, nc = _normalize_completion(user), _normalize_completion(correct)
        if nu == nc:
            return True
        # Plural variants
        for suffix in ["s", "es"]:
            if nu + suffix == nc or nc + suffix == nu:
                return True
        # 1-edit distance tolerance for longer words
        if len(nu) >= 4 and len(nc) >= 4:
            if abs(len(nu) - len(nc)) <= 1:
                diffs = sum(1 for a, b in zip(nu, nc) if a != b) + abs(len(nu) - len(nc))
                if diffs <= 1:
                    return True
        return False

    questions = content.get("questions", {})
    groups = questions.get("groups", [])

    if skill in ("reading", "grammar") and groups:
        # New format: groups with type field
        for gi, group in enumerate(groups):
            gtype = group.get("type", "unknown")
            if gtype == "matching_headings":
                group_answers = group.get("answers", [])
                for ans in group_answers:
                    pnum = ans.get("paragraph_number", "")
                    key = f"mh_{gi}_{pnum}"
                    user_ans = answers.get(key, "")
                    correct_ans = ans.get("answer", "")
                    inc(gtype, user_ans == correct_ans)
            else:
                items = group.get("items", [])
                for item in items:
                    qnum = item.get("question_number", "")
                    key = f"q_{gi}_{qnum}"
                    user_ans = answers.get(key, "")
                    correct_ans = item.get("answer", "")
                    if gtype in ("true_false_not_given", "multiple_choice", "matching_information"):
                        inc(gtype, user_ans == correct_ans)
                    else:
                        # completion types, short_answer
                        inc(gtype, _completion_match(user_ans, correct_ans))

    elif skill == "reading" and not groups:
        # Legacy format: tfng_*, mc_*, mh_* keys
        answer_key = content.get("answer_key", {})
        tfng_answers = answer_key.get("true_false_not_given", [])
        for tfa in tfng_answers:
            qnum = tfa.get("question_number", "")
            key = f"tfng_{qnum}"
            user_ans = answers.get(key, "")
            inc("true_false_not_given", user_ans == tfa.get("answer", ""))

        second_type = answer_key.get("second_type", "")
        second_answers = answer_key.get(second_type, [])
        if second_type == "multiple_choice":
            for i, item in enumerate(second_answers):
                key = f"mc_{i}"
                user_ans = answers.get(key, "")
                inc("multiple_choice", user_ans == item.get("answer", ""))
        elif second_type == "matching_headings":
            for item in second_answers:
                pnum = item.get("paragraph_number", "")
                key = f"mh_{pnum}"
                user_ans = answers.get(key, "")
                inc("matching_headings", user_ans == item.get("answer", ""))

    elif skill == "listening":
        qs = questions if isinstance(questions, list) else content.get("questions", [])
        if not isinstance(qs, list):
            qs = []

        # Count completion and MCQ questions to reconstruct index mapping
        completion_qs = [q for q in qs if q.get("type") == "completion"]
        mcq_qs = [q for q in qs if q.get("type") == "mcq"]
        matching_blocks = content.get("matching", [])

        for i, q in enumerate(completion_qs):
            key = f"comp_{i}"
            user_ans = answers.get(key, "")
            inc("completion", _completion_match(user_ans, q.get("answer", "")))

        for i, q in enumerate(mcq_qs):
            key = f"mc_{i}"
            user_ans = (answers.get(key, "") or "").strip().upper()
            inc("multiple_choice", user_ans == (q.get("answer", "") or "").strip().upper())

        for bi, block in enumerate(matching_blocks):
            block_answers = block.get("answers", {})
            stems = block.get("stems", [])
            for stem in stems:
                qnum = stem.get("question_number", "")
                key = f"match_{bi}_{qnum}"
                user_ans = (answers.get(key, "") or "").strip().upper()
                correct_ans = (block_answers.get(str(qnum), "") or "").strip().upper()
                inc("matching", user_ans == correct_ans)

    return stats


@router.get("/progress/accuracy-insights")
def get_accuracy_insights(
    skill: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate accuracy data for reading, listening, or grammar."""
    valid_skills = {"reading", "listening", "grammar"}
    if skill not in valid_skills:
        from fastapi import HTTPException
        raise HTTPException(400, f"Invalid skill. Must be one of: {', '.join(valid_skills)}")

    rows = (
        db.query(UserPractice, GeneratedPractice)
        .join(GeneratedPractice, UserPractice.practice_id == GeneratedPractice.id)
        .filter(
            UserPractice.user_id == current_user.id,
            GeneratedPractice.skill == skill,
            UserPractice.submitted_at.isnot(None),
        )
        .order_by(UserPractice.submitted_at.desc())
        .all()
    )

    sessions = []
    # Accumulate question-type stats across all sessions
    qtype_totals: dict = {}  # {type: {"correct": int, "total": int}}

    for up, gp in rows:
        correct = up.correct_count or 0
        total_q = up.total_questions or 0
        accuracy = round(correct / total_q * 100, 1) if total_q > 0 else 0
        sessions.append({
            "score": float(up.score) if up.score else 0,
            "correct": correct,
            "total_questions": total_q,
            "accuracy": accuracy,
            "date": up.submitted_at.isoformat() if up.submitted_at else None,
            "topic": gp.topic,
        })

        # Parse per-question-type stats for this session
        try:
            session_qtype = _extract_question_type_stats(
                up.user_answers, gp.content, skill
            )
            for qtype, counts in session_qtype.items():
                if qtype not in qtype_totals:
                    qtype_totals[qtype] = {"correct": 0, "total": 0}
                qtype_totals[qtype]["correct"] += counts["correct"]
                qtype_totals[qtype]["total"] += counts["total"]
        except Exception:
            # If parsing fails for a session, skip its breakdown contribution
            logger.debug("Failed to parse question_type stats for practice %s", up.practice_id, exc_info=True)

    total = len(sessions)
    if total == 0:
        return {
            "total_sessions": 0,
            "overall_accuracy": None,
            "accuracy_trend": "insufficient",
            "overall_average_band": None,
            "best_accuracy": None,
            "worst_accuracy": None,
            "total_questions_answered": 0,
            "total_correct": 0,
            "recent_sessions": [],
            "question_type_breakdown": [],
        }

    all_accuracy = [s["accuracy"] for s in sessions]
    all_bands = [s["score"] for s in sessions if s["score"] > 0]
    overall_accuracy = round(sum(all_accuracy) / len(all_accuracy), 1)

    # Trend: last 3 vs previous 3
    if total >= 6:
        recent_3 = all_accuracy[:3]
        prev_3 = all_accuracy[3:6]
        delta = (sum(recent_3) / len(recent_3)) - (sum(prev_3) / len(prev_3))
        accuracy_trend = "improving" if delta > 5 else "declining" if delta < -5 else "stable"
    else:
        accuracy_trend = "insufficient"

    recent = [
        {
            "date": s["date"],
            "score": s["score"],
            "accuracy": s["accuracy"],
            "correct": s["correct"],
            "total_questions": s["total_questions"],
            "topic": s["topic"],
        }
        for s in sessions[:5]
    ]

    # Build question_type_breakdown sorted by total (descending)
    question_type_breakdown = []
    for qtype, counts in sorted(qtype_totals.items(), key=lambda x: x[1]["total"], reverse=True):
        t = counts["total"]
        c = counts["correct"]
        question_type_breakdown.append({
            "type": qtype,
            "correct": c,
            "total": t,
            "accuracy": round(c / t * 100, 1) if t > 0 else 0,
        })

    return {
        "total_sessions": total,
        "overall_accuracy": overall_accuracy,
        "accuracy_trend": accuracy_trend,
        "overall_average_band": round(sum(all_bands) / len(all_bands) * 2) / 2 if all_bands else None,
        "best_accuracy": max(all_accuracy),
        "worst_accuracy": min(all_accuracy),
        "total_questions_answered": sum(s["total_questions"] for s in sessions),
        "total_correct": sum(s["correct"] for s in sessions),
        "recent_sessions": recent,
        "question_type_breakdown": question_type_breakdown,
    }