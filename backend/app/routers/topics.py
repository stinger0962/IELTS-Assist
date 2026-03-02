from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from app.database import get_db
from app.models.models import User, Topic, TopicReview, SkillType
from app.schemas.schemas import TopicResponse, FlashCardResponse, TopicReviewCreate
from app.services.auth import get_current_user

router = APIRouter()

# Sample topics data
SAMPLE_TOPICS = [
    # Vocabulary
    {"skill": "reading", "category": "vocabulary", "title": "Academic Vocabulary - Cause & Effect", "content": "Cause and effect vocabulary: consequently, therefore, thus, hence, as a result, due to, owing to, because of, lead to, result in, give rise to, contribute to.", "content_zh": "因果词汇：因此、所以、因而、导致、由于、因为、引起、结果是、促成。", "difficulty": 2},
    {"skill": "reading", "category": "vocabulary", "title": "Academic Vocabulary - Comparison", "content": "Comparison words: similarly, likewise, in comparison, by contrast, whereas, while, on the other hand, nevertheless, nonetheless, despite, in spite of.", "content_zh": "对比词汇：同样地、相比之下、然而、虽然、尽管、不过。", "difficulty": 2},
    {"skill": "listening", "category": "vocabulary", "title": "Common Listening Phrases", "content": "Signposting language: I'd like to, I'd prefer to, the main point is, essentially, basically, in summary, to sum up, moving on to, regarding.", "content_zh": "信号词：我想、主要是、基本上、总结一下、转到、关于。", "difficulty": 1},
    {"skill": "speaking", "category": "vocabulary", "title": "Speaking Connectors", "content": "Speaking connectors: well, actually, you know, I mean, you see, the thing is, in my opinion, from my point of view, as far as I'm concerned.", "content_zh": "口语连接词：其实、你知道、我的意思是、在我看来。", "difficulty": 1},
    {"skill": "writing", "category": "topic_idea", "title": "Education Topics", "content": "Key points: University education should be free. Benefits: equal opportunities, more educated citizens. Arguments against: tax payer burden, some students may not value it.", "content_zh": "关键观点：大学教育应该免费。好处：机会平等。反对：纳税人负担。", "difficulty": 2},
    {"skill": "writing", "category": "topic_idea", "title": "Technology & Society", "content": "Key points: Technology improves quality of life. Concerns: addiction, social isolation, privacy. Balance: use technology wisely, digital wellbeing.", "content_zh": "关键观点：技术提高生活质量。担忧：成瘾、隐私。平衡：明智使用。", "difficulty": 2},
    # Grammar
    {"skill": "reading", "category": "grammar", "title": "Passive Voice in Academic Writing", "content": "Use passive when: the action is more important than the agent, subject is unknown, you want to sound objective. Example: 'The experiment was conducted...' not 'We conducted the experiment...'", "content_zh": "使用被动语态：当动作比执行者更重要时、主体未知时、想显得客观。", "difficulty": 3},
    {"skill": "writing", "category": "grammar", "title": "Complex Sentences", "content": "Use relative clauses: 'The book, which was written in 1990, is still popular.' Use conditional: 'If more people cycled, there would be less pollution.'", "content_zh": "使用定语从句和条件句来丰富写作。", "difficulty": 3},
    # Speaking Topics
    {"skill": "speaking", "category": "topic_idea", "title": "Hometown", "content": "Describe your hometown: location, size, population, history, famous places, what you like/dislike, whether you would recommend it to visitors.", "content_zh": "描述你的家乡：位置、大小、人口、历史、著名地点、喜好。", "difficulty": 1},
    {"skill": "speaking", "category": "topic_idea", "title": "Work or Studies", "content": "Describe your job/studies: what you do, why you chose it, how long you've been doing it, whether you enjoy it, future plans.", "content_zh": "描述你的工作/学习：做什么、为什么选择、做了多久、是否喜欢。", "difficulty": 1},
    {"skill": "speaking", "category": "topic_idea", "title": "Hobbies & Interests", "content": "Describe a hobby: how you became interested, how often you do it, benefits, who you do it with, why it is important to you.", "content_zh": "描述一个爱好：如何感兴趣、多久做一次、好处、和谁一起。", "difficulty": 1},
]

def init_sample_topics(db: Session):
    if db.query(Topic).count() == 0:
        for topic_data in SAMPLE_TOPICS:
            topic = Topic(
                skill=SkillType(topic_data["skill"]),
                category=topic_data["category"],
                title=topic_data["title"],
                content=topic_data["content"],
                content_zh=topic_data.get("content_zh"),
                difficulty=topic_data.get("difficulty", 1)
            )
            db.add(topic)
        db.commit()

@router.get("", response_model=List[TopicResponse])
def get_topics(
    skill: SkillType = None,
    category: str = None,
    difficulty: int = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Initialize sample topics if none exist
    init_sample_topics(db)
    
    query = db.query(Topic)
    if skill:
        query = query.filter(Topic.skill == skill)
    if category:
        query = query.filter(Topic.category == category)
    if difficulty:
        query = query.filter(Topic.difficulty == difficulty)
    return query.limit(limit).all()

@router.get("/flashcards", response_model=List[FlashCardResponse])
def get_flashcards(
    skill: SkillType = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Initialize sample topics if none exist
    init_sample_topics(db)
    
    # Get topics that need review (no review record or past due)
    now = datetime.utcnow()
    
    query = db.query(Topic).join(TopicReview, Topic.id == TopicReview.topic_id, isouter=True).filter(
        (TopicReview.next_review == None) | (TopicReview.next_review <= now)
    )
    
    if skill:
        query = query.filter(Topic.skill == skill)
    
    topics = query.limit(limit).all()
    
    results = []
    for topic in topics:
        review = db.query(TopicReview).filter(
            TopicReview.user_id == current_user.id,
            TopicReview.topic_id == topic.id
        ).first()
        
        if review:
            results.append(FlashCardResponse(
                topic=topic,
                next_review=review.next_review,
                ease_factor=review.ease_factor,
                interval_days=review.interval_days,
                repetitions=review.repetitions
            ))
        else:
            results.append(FlashCardResponse(
                topic=topic,
                next_review=None,
                ease_factor=2.5,
                interval_days=1,
                repetitions=0
            ))
    
    return results

@router.post("/review")
def review_topic(
    review: TopicReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    topic = db.query(Topic).filter(Topic.id == review.topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    existing = db.query(TopicReview).filter(
        TopicReview.user_id == current_user.id,
        TopicReview.topic_id == review.topic_id
    ).first()
    
    if existing:
        # SM-2 algorithm simplified
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
        # Create new review record
        interval_days = 1 if review.quality < 3 else 1
        next_review = datetime.utcnow() + timedelta(days=interval_days)
        
        new_review = TopicReview(
            user_id=current_user.id,
            topic_id=review.topic_id,
            next_review=next_review,
            ease_factor=2.5,
            interval_days=interval_days,
            repetitions=1 if review.quality >= 3 else 0,
            last_reviewed=datetime.utcnow()
        )
        db.add(new_review)
        db.commit()
        return new_review