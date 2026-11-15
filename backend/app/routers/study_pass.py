from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import User
from app.services.study_pass import study_pass_status
from app.services.auth import get_current_user

router = APIRouter()


@router.get("")
def get_study_pass(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return study_pass_status(db, user)
