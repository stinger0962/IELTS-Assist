import logging
import sys
import traceback
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from typing import List, Optional

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.models import Topic, TopicReview, SkillType, User
from app.schemas.schemas import FlashCardResponse, TopicCreate, TopicResponse, TopicReviewCreate
from app.services.auth import get_current_user

router = APIRouter()

# ── Sample global topics (seeded once, user_id=NULL) ─────────────────────────

SAMPLE_TOPICS = [
    {"skill": "reading", "category": "vocabulary", "title": "Academic Vocabulary - Cause & Effect", "content": "Cause and effect vocabulary: consequently, therefore, thus, hence, as a result, due to, owing to, because of, lead to, result in, give rise to, contribute to.", "content_zh": "因果词汇：因此、所以、因而、导致、由于、因为、引起、结果是、促成。", "difficulty": 2},
    {"skill": "reading", "category": "vocabulary", "title": "Academic Vocabulary - Comparison", "content": "Comparison words: similarly, likewise, in comparison, by contrast, whereas, while, on the other hand, nevertheless, nonetheless, despite, in spite of.", "content_zh": "对比词汇：同样地、相比之下、然而、虽然、尽管、不过。", "difficulty": 2},
    {"skill": "listening", "category": "vocabulary", "title": "Common Listening Phrases", "content": "Signposting language: I'd like to, I'd prefer to, the main point is, essentially, basically, in summary, to sum up, moving on to, regarding.", "content_zh": "信号词：我想、主要是、基本上、总结一下、转到、关于。", "difficulty": 1},
    {"skill": "speaking", "category": "vocabulary", "title": "Speaking Connectors", "content": "Speaking connectors: well, actually, you know, I mean, you see, the thing is, in my opinion, from my point of view, as far as I'm concerned.", "content_zh": "口语连接词：其实、你知道、我的意思是、在我看来。", "difficulty": 1},
    {"skill": "writing", "category": "topic_idea", "title": "Education Topics", "content": "Key points: University education should be free. Benefits: equal opportunities, more educated citizens. Arguments against: tax payer burden, some students may not value it.", "content_zh": "关键观点：大学教育应该免费。好处：机会平等。反对：纳税人负担。", "difficulty": 2},
    {"skill": "writing", "category": "topic_idea", "title": "Technology & Society", "content": "Key points: Technology improves quality of life. Concerns: addiction, social isolation, privacy. Balance: use technology wisely, digital wellbeing.", "content_zh": "关键观点：技术提高生活质量。担忧：成瘾、隐私。平衡：明智使用。", "difficulty": 2},
    {"skill": "reading", "category": "grammar", "title": "Passive Voice in Academic Writing", "content": "Use passive when: the action is more important than the agent, subject is unknown, you want to sound objective. Example: 'The experiment was conducted...' not 'We conducted the experiment...'", "content_zh": "使用被动语态：当动作比执行者更重要时、主体未知时、想显得客观。", "difficulty": 3},
    {"skill": "writing", "category": "grammar", "title": "Complex Sentences", "content": "Use relative clauses: 'The book, which was written in 1990, is still popular.' Use conditional: 'If more people cycled, there would be less pollution.'", "content_zh": "使用定语从句和条件句来丰富写作。", "difficulty": 3},
    {"skill": "speaking", "category": "topic_idea", "title": "Hometown", "content": "Describe your hometown: location, size, population, history, famous places, what you like/dislike, whether you would recommend it to visitors.", "content_zh": "描述你的家乡：位置、大小、人口、历史、著名地点、喜好。", "difficulty": 1},
    {"skill": "speaking", "category": "topic_idea", "title": "Work or Studies", "content": "Describe your job/studies: what you do, why you chose it, how long you've been doing it, whether you enjoy it, future plans.", "content_zh": "描述你的工作/学习：做什么、为什么选择、做了多久、是否喜欢。", "difficulty": 1},
    {"skill": "speaking", "category": "topic_idea", "title": "Hobbies & Interests", "content": "Describe a hobby: how you became interested, how often you do it, benefits, who you do it with, why it is important to you.", "content_zh": "描述一个爱好：如何感兴趣、多久做一次、好处、和谁一起。", "difficulty": 1},
]


def init_sample_topics(db: Session):
    """Seed global (user_id=NULL) topics once."""
    if db.query(Topic).filter(Topic.user_id.is_(None)).count() == 0:
        for d in SAMPLE_TOPICS:
            db.add(Topic(
                skill=SkillType(d["skill"]),
                category=d["category"],
                title=d["title"],
                content=d["content"],
                content_zh=d.get("content_zh"),
                difficulty=d.get("difficulty", 1),
                user_id=None,
            ))
        db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[TopicResponse])
def get_topics(
    skill: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[int] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info("get_topics: user=%s skill=%r category=%r", current_user.id, skill, category)
    try:
        init_sample_topics(db)
        query = db.query(Topic).filter(
            (Topic.user_id == current_user.id) | (Topic.user_id.is_(None))
        )
        if skill:
            try:
                query = query.filter(Topic.skill == SkillType(skill))
            except ValueError:
                pass
        if category:
            query = query.filter(Topic.category == category)
        if difficulty:
            query = query.filter(Topic.difficulty == difficulty)
        results = query.order_by(Topic.id.desc()).limit(limit).all()
        deck_ids = {
            row[0] for row in db.query(TopicReview.topic_id)
            .filter(TopicReview.user_id == current_user.id)
            .all()
        }
        logger.info("get_topics: returning %d topics", len(results))
        return [
            TopicResponse(
                id=t.id, user_id=t.user_id, skill=t.skill, category=t.category,
                title=t.title, content=t.content, content_zh=t.content_zh,
                example=t.example, example_zh=t.example_zh, difficulty=t.difficulty,
                phonetic=t.phonetic, audio_url=t.audio_url,
                in_deck=t.id in deck_ids,
            )
            for t in results
        ]
    except Exception:
        tb = traceback.format_exc()
        logger.error("get_topics failed:\n%s", tb)
        print(f"[IELTS ERROR] get_topics\n{tb}", file=sys.stderr, flush=True)
        raise


@router.post("", response_model=TopicResponse)
def create_topic(
    topic: TopicCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a personal vocabulary word for the current user."""
    logger.info("create_topic: user=%s title=%r skill=%r", current_user.id, topic.title, topic.skill)
    try:
        db_topic = Topic(
            user_id=current_user.id,
            skill=SkillType(topic.skill),
            category=topic.category,
            title=topic.title,
            content=topic.content,
            content_zh=topic.content_zh,
            example=topic.example,
            phonetic=topic.phonetic,
            audio_url=topic.audio_url,
            difficulty=2,
        )
        db.add(db_topic)
        db.commit()
        db.refresh(db_topic)
        logger.info("create_topic: inserted topic id=%s", db_topic.id)
        # Auto-add to user's flashcard queue (due immediately)
        db.add(TopicReview(
            user_id=current_user.id,
            topic_id=db_topic.id,
            next_review=datetime.utcnow(),
            ease_factor=2.5,
            interval_days=1,
            repetitions=0,
        ))
        db.commit()
        logger.info("create_topic: review record inserted for topic id=%s", db_topic.id)
        return TopicResponse(
            id=db_topic.id, user_id=db_topic.user_id, skill=db_topic.skill,
            category=db_topic.category, title=db_topic.title, content=db_topic.content,
            content_zh=db_topic.content_zh, example=db_topic.example,
            example_zh=db_topic.example_zh, difficulty=db_topic.difficulty,
            phonetic=db_topic.phonetic, audio_url=db_topic.audio_url,
            in_deck=True,
        )
    except Exception:
        db.rollback()
        tb = traceback.format_exc()
        logger.error("create_topic failed:\n%s", tb)
        print(f"[IELTS ERROR] create_topic\n{tb}", file=sys.stderr, flush=True)
        raise


@router.post("/{topic_id}/add-to-deck")
def add_to_deck(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a topic to the user's flashcard deck (idempotent — no-op if already in deck)."""
    logger.info("add_to_deck: user=%s topic_id=%s", current_user.id, topic_id)
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    existing = db.query(TopicReview).filter(
        TopicReview.user_id == current_user.id,
        TopicReview.topic_id == topic_id,
    ).first()
    if existing:
        return {"added": False}
    try:
        db.add(TopicReview(
            user_id=current_user.id,
            topic_id=topic_id,
            next_review=datetime.utcnow(),
            ease_factor=2.5,
            interval_days=1,
            repetitions=0,
        ))
        db.commit()
        return {"added": True}
    except Exception:
        db.rollback()
        logger.error("add_to_deck failed:\n%s", traceback.format_exc())
        raise


@router.delete("/{topic_id}/remove-from-deck")
def remove_from_deck(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a topic from the user's flashcard deck (deletes review record)."""
    logger.info("remove_from_deck: user=%s topic_id=%s", current_user.id, topic_id)
    review = db.query(TopicReview).filter(
        TopicReview.user_id == current_user.id,
        TopicReview.topic_id == topic_id,
    ).first()
    if not review:
        return {"removed": False}
    try:
        db.delete(review)
        db.commit()
        return {"removed": True}
    except Exception:
        db.rollback()
        logger.error("remove_from_deck failed:\n%s", traceback.format_exc())
        raise


@router.get("/flashcards", response_model=List[FlashCardResponse])
def get_flashcards(
    skill: Optional[str] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    init_sample_topics(db)
    now = datetime.utcnow()

    # Inner join — only topics the user has explicitly added to their deck and are due
    query = (
        db.query(Topic, TopicReview)
        .join(
            TopicReview,
            and_(Topic.id == TopicReview.topic_id, TopicReview.user_id == current_user.id),
        )
        .filter(TopicReview.next_review <= now)
    )
    if skill:
        try:
            query = query.filter(Topic.skill == SkillType(skill))
        except ValueError:
            pass

    rows = query.limit(limit).all()
    return [
        FlashCardResponse(
            topic=TopicResponse(
                id=topic.id, user_id=topic.user_id, skill=topic.skill,
                category=topic.category, title=topic.title, content=topic.content,
                content_zh=topic.content_zh, example=topic.example,
                example_zh=topic.example_zh, difficulty=topic.difficulty,
                phonetic=topic.phonetic, audio_url=topic.audio_url,
                in_deck=True,
            ),
            next_review=review.next_review,
            ease_factor=review.ease_factor,
            interval_days=review.interval_days,
            repetitions=review.repetitions,
        )
        for topic, review in rows
    ]


@router.get("/due-count")
def get_due_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return count of flashcards due for review today."""
    now = datetime.utcnow()
    try:
        count = (
            db.query(func.count(TopicReview.id))
            .filter(
                TopicReview.user_id == current_user.id,
                TopicReview.next_review <= now,
            )
            .scalar()
        )
        logger.info("get_due_count: user=%s due=%s", current_user.id, count)
        return {"due": count or 0}
    except Exception:
        tb = traceback.format_exc()
        logger.error("get_due_count failed:\n%s", tb)
        print(f"[IELTS ERROR] get_due_count\n{tb}", file=sys.stderr, flush=True)
        raise


@router.post("/review")
def review_topic(
    review: TopicReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    topic = db.query(Topic).filter(Topic.id == review.topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    existing = db.query(TopicReview).filter(
        TopicReview.user_id == current_user.id,
        TopicReview.topic_id == review.topic_id,
    ).first()

    if existing:
        quality = review.quality
        if quality >= 3:
            if existing.repetitions == 0:
                existing.interval_days = 1
            elif existing.repetitions == 1:
                existing.interval_days = 6
            else:
                existing.interval_days = int(existing.interval_days * existing.ease_factor)
            existing.repetitions += 1
            existing.ease_factor = max(1.3, existing.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        else:
            existing.repetitions = 0
            existing.interval_days = 1
        existing.last_reviewed = datetime.utcnow()
        existing.next_review = datetime.utcnow() + timedelta(days=existing.interval_days)
        db.commit()
        return existing
    else:
        interval_days = 1
        new_review = TopicReview(
            user_id=current_user.id,
            topic_id=review.topic_id,
            next_review=datetime.utcnow() + timedelta(days=interval_days),
            ease_factor=2.5,
            interval_days=interval_days,
            repetitions=1 if review.quality >= 3 else 0,
            last_reviewed=datetime.utcnow(),
        )
        db.add(new_review)
        db.commit()
        return new_review
