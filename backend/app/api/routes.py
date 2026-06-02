from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.schemas import AnswerRequest, AnswerResponse, RoleOption, SessionResponse, SessionSummary
from app.services.interview import (
    available_roles,
    create_session,
    get_session_or_404,
    respond_to_question,
    serialize_session,
    serialize_summary,
)
from app.services.resume_parser import extract_resume_text
from app.services.vector_store import VectorStore


router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "knowledge_chunks": VectorStore().count_chunks()}


@router.get("/roles", response_model=list[RoleOption])
def roles() -> list[dict]:
    return available_roles()


@router.post("/sessions", response_model=SessionResponse)
async def start_session(
    role: str = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    try:
        resume_text = await extract_resume_text(resume)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = create_session(db, role=role, resume_text=resume_text)
    return serialize_session(session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db)) -> dict:
    return serialize_session(get_session_or_404(db, session_id))


@router.post("/sessions/{session_id}/answers", response_model=AnswerResponse)
def submit_answer(session_id: str, payload: AnswerRequest, db: Session = Depends(get_db)) -> dict:
    score, next_turn, summary = respond_to_question(
        db,
        session_id=session_id,
        answer=payload.answer,
        limit=get_settings().interview_question_limit,
    )
    session = get_session_or_404(db, session_id)
    return {
        "session_id": session_id,
        "status": session.status,
        "answer_score": score,
        "next_question": next_turn and serialize_session(session)["current_question"],
        "summary": summary,
    }


@router.get("/sessions/{session_id}/summary", response_model=SessionSummary)
def summary(session_id: str, db: Session = Depends(get_db)) -> dict:
    return serialize_summary(get_session_or_404(db, session_id))
