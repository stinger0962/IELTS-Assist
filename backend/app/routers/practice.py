from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import User, PracticeResult, SkillType
from app.schemas.schemas import PracticeResultCreate, PracticeResultResponse
from app.services.auth import get_current_user

router = APIRouter()

# Sample practice data
SAMPLE_READING_PASSAGES = [
    {
        "id": "reading_1",
        "title": "The History of Coffee",
        "content": """Coffee is a brewed drink prepared from roasted coffee beans, the seeds of berries from certain Coffea species. From the coffee bean, the drink has become a global phenomenon.

Coffee is darkly colored, bitter, slightly acidic and has a stimulating effect on humans, primarily due to its caffeine content. It is one of the most consumed drinks in the world.

The history of coffee dates back to the 15th century, and possibly earlier with a number of legends surrounding its first use. The coffee plant originated in the highlands of Ethiopia, according to legend discovered by a goat herder named Kaldi.""",
        "questions": [
            {"id": "q1", "question": "What is coffee made from?", "options": ["Tea leaves", "Roasted beans", "Cocoa pods", "Rice"], "answer": 1},
            {"id": "q2", "question": "Where did coffee originate?", "options": ["Brazil", "Ethiopia", "Colombia", "Vietnam"], "answer": 1},
            {"id": "q3", "question": "What gives coffee its stimulating effect?", "options": ["Sugar", "Caffeine", "Milk", "Chocolate"], "answer": 1}
        ]
    },
    {
        "id": "reading_2",
        "title": "Renewable Energy Sources",
        "content": """Renewable energy is energy derived from natural sources that are replenished at a higher rate than they are consumed. Solar and wind are two examples of renewable energy sources.

Solar energy is radiant light and heat from the Sun that is harnessed using a range of technologies. Solar panels convert sunlight into electricity.

Wind energy is the process of creating electricity using the wind, or air flows. Wind turbines convert the kinetic energy of wind into mechanical power.""",
        "questions": [
            {"id": "q1", "question": "What is a key characteristic of renewable energy?", "options": ["It is non-replenishable", "It is replenished faster than consumed", "It causes pollution", "It is expensive"], "answer": 1},
            {"id": "q2", "question": "What do solar panels convert?", "options": ["Wind to electricity", "Sunlight to electricity", "Water to electricity", "Heat to electricity"], "answer": 1}
        ]
    }
]

SAMPLE_LISTENING_EXERCISES = [
    {
        "id": "listening_1",
        "title": "Campus Tour",
        "script": """Welcome to Oxford University. I'm your tour guide today. We'll start at the main entrance and visit the most important buildings.

The library is located to the north of the main quad. It contains over 12 million printed items. The opening hours are from 8 am to midnight.

Next, we'll visit the science building. This is where the physics and chemistry departments are located. The building has 15 laboratories and a large lecture hall that seats 500 people.

Finally, we'll end our tour at the student center where you can find the cafeteria and recreational facilities.""",
        "questions": [
            {"id": "q1", "question": "Where is the library located?", "options": ["South of main quad", "North of main quad", "East of main quad", "West of main quad"], "answer": 1},
            {"id": "q2", "question": "How many laboratories are in the science building?", "options": ["10", "12", "15", "20"], "answer": 2},
            {"id": "q3", "question": "What time does the library close?", "options": ["10 pm", "11 pm", "Midnight", "1 am"], "answer": 2}
        ]
    }
]

SAMPLE_WRITING_TOPICS = [
    {"id": "writing_1", "type": "task2", "question": "Some people believe that unpaid community service should be a compulsory part of high school programs. To what extent do you agree or disagree?"},
    {"id": "writing_2", "type": "task2", "question": "In many countries, the amount of crime is increasing. What do you think are the main causes of crime? How can we reduce crime rates?"},
    {"id": "writing_3", "type": "task1", "question": "The table below shows the number of library books read by boys and girls in a particular school from 2006 to 2013. Summarise the information by selecting and reporting the main features."}
]

SAMPLE_SPEAKING_TOPICS = [
    {"id": "speaking_1", "part": "part2", "question": "Describe a skill you learned when you were a child. You should say: what the skill was, who taught you, how you learned it, and explain why it was useful."},
    {"id": "speaking_2", "part": "part2", "question": "Describe a place you would like to visit. You should say: where it is, what you would do there, who you would go with, and explain why you want to visit."},
    {"id": "speaking_3", "part": "part3", "question": "What are the benefits of traveling? How has travel changed in recent years?"}
]

@router.get("/reading")
def get_reading_exercises():
    return SAMPLE_READING_PASSAGES

@router.get("/listening")
def get_listening_exercises():
    return SAMPLE_LISTENING_EXERCISES

@router.get("/writing")
def get_writing_topics():
    return SAMPLE_WRITING_TOPICS

@router.get("/speaking")
def get_speaking_topics():
    return SAMPLE_SPEAKING_TOPICS

@router.post("/submit", response_model=PracticeResultResponse)
def submit_practice(
    result: PracticeResultCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_result = PracticeResult(
        user_id=current_user.id,
        skill=result.skill,
        exercise_id=result.exercise_id,
        score=result.score,
        total_questions=result.total_questions,
        correct_answers=result.correct_answers,
        time_taken_seconds=result.time_taken_seconds
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result

@router.get("/history", response_model=List[PracticeResultResponse])
def get_practice_history(
    skill: SkillType = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(PracticeResult).filter(PracticeResult.user_id == current_user.id)
    if skill:
        query = query.filter(PracticeResult.skill == skill)
    return query.order_by(PracticeResult.created_at.desc()).limit(limit).all()