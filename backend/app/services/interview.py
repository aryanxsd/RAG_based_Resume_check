from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import InterviewSession, InterviewTurn
from app.schemas import QuestionPayload, RetrievedContext
from app.services.rag import (
    build_topics,
    dumps,
    generate_question,
    loads,
    retrieve_context,
    score_answer,
)
from app.services.resume_parser import extract_skills, infer_candidate_name, infer_domains
from app.services.role_profiles import ROLE_LABELS, ROLE_OPTIONS


def _as_question_payload(turn: InterviewTurn) -> QuestionPayload:
    return QuestionPayload(
        turn_number=turn.turn_number,
        question=turn.question,
        difficulty=turn.difficulty,
        retrieved_context=[RetrievedContext(**item) for item in loads(turn.retrieved_context_json, [])],
        generation_trace=loads(turn.generation_trace_json, {}),
    )


def create_session(db: Session, *, role: str, resume_text: str) -> InterviewSession:
    if role not in ROLE_LABELS:
        raise HTTPException(status_code=400, detail="Unsupported role selected.")

    skills = extract_skills(resume_text)
    domains = infer_domains(skills, resume_text)
    topics = build_topics(role, skills, domains)
    session = InterviewSession(
        role=role,
        candidate_name=infer_candidate_name(resume_text),
        resume_text=resume_text,
        extracted_skills_json=dumps(skills),
        domains_json=dumps(domains),
        topics_json=dumps(topics),
    )
    db.add(session)
    db.flush()
    create_next_question(db, session)
    db.commit()
    db.refresh(session)
    return session


def create_next_question(db: Session, session: InterviewSession, previous_answer: str | None = None) -> InterviewTurn:
    skills = loads(session.extracted_skills_json, [])
    domains = loads(session.domains_json, [])
    query, context = retrieve_context(
        role=session.role,
        resume_text=session.resume_text,
        skills=skills,
        domains=domains,
        previous_answer=previous_answer,
    )
    if not context:
        raise HTTPException(
            status_code=503,
            detail="Knowledge base is empty. Run backend/scripts/ingest.py before starting an interview.",
        )

    turn_number = session.current_question_index + 1
    question, trace, difficulty = generate_question(
        role=session.role,
        role_label=ROLE_LABELS[session.role],
        turn_number=turn_number,
        skills=skills,
        domains=domains,
        retrieved_context=context,
        previous_answer=previous_answer,
    )
    trace["retrieval_query"] = query
    turn = InterviewTurn(
        session_id=session.id,
        turn_number=turn_number,
        question=question,
        retrieved_context_json=dumps(context),
        generation_trace_json=dumps(trace),
        difficulty=difficulty,
    )
    session.current_question_index = turn_number
    session.updated_at = datetime.now(timezone.utc)
    db.add(turn)
    db.flush()
    return turn


def get_session_or_404(db: Session, session_id: str) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    return session


def respond_to_question(db: Session, session_id: str, answer: str, limit: int) -> tuple[dict, InterviewTurn | None, dict | None]:
    session = get_session_or_404(db, session_id)
    if session.status == "completed":
        return {"score": 0, "feedback": "Session already completed.", "matched_terms": []}, None, loads(session.summary_json, {})

    current_turn = next((turn for turn in reversed(session.turns) if turn.answer is None), None)
    if not current_turn:
        raise HTTPException(status_code=409, detail="No pending question found for this session.")

    context = loads(current_turn.retrieved_context_json, [])
    score = score_answer(answer, context)
    current_turn.answer = answer
    current_turn.answer_score_json = dumps(score)

    if session.current_question_index >= limit:
        session.status = "completed"
        summary = build_summary(session)
        session.summary_json = dumps(summary)
        session.updated_at = datetime.now(timezone.utc)
        db.commit()
        return score, None, summary

    next_turn = create_next_question(db, session, previous_answer=answer)
    db.commit()
    db.refresh(next_turn)
    return score, next_turn, None


def build_summary(session: InterviewSession) -> dict:
    scores = [loads(turn.answer_score_json, {}).get("score", 0) for turn in session.turns if turn.answer_score_json]
    average = round(sum(scores) / len(scores), 1) if scores else 0
    skills = loads(session.extracted_skills_json, [])
    topics = loads(session.topics_json, [])
    strengths = []
    gaps = []
    for turn in session.turns:
        score = loads(turn.answer_score_json, {}).get("score", 0)
        trace = loads(turn.generation_trace_json, {})
        keywords = trace.get("keywords", [])
        if score >= 65 and keywords:
            strengths.append(keywords[0])
        elif keywords:
            gaps.append(keywords[0])

    return {
        "overall_score": average,
        "readiness_band": "strong" if average >= 75 else "promising" if average >= 50 else "needs more depth",
        "skills_detected": skills,
        "topics_evaluated": topics,
        "strengths": sorted(set(strengths))[:5],
        "gaps": sorted(set(gaps))[:5],
        "recommendation": _recommendation(average),
        "traceability_note": "Each question stores retrieved chunk ids, source titles, candidate signals, and answer scoring terms.",
    }


def _recommendation(score: float) -> str:
    if score >= 75:
        return "Advance to a deeper technical round with project-specific design questions."
    if score >= 50:
        return "Proceed with a focused follow-up round on the listed gaps."
    return "Ask for a practical take-home or foundational refresh before advancing."


def serialize_session(session: InterviewSession) -> dict:
    pending = next((turn for turn in reversed(session.turns) if turn.answer is None), None)
    return {
        "session_id": session.id,
        "role": session.role,
        "candidate_name": session.candidate_name,
        "extracted_skills": loads(session.extracted_skills_json, []),
        "domains": loads(session.domains_json, []),
        "topics": loads(session.topics_json, []),
        "status": session.status,
        "current_question": _as_question_payload(pending) if pending else None,
    }


def serialize_summary(session: InterviewSession) -> dict:
    summary = loads(session.summary_json, None) or build_summary(session)
    return {
        "session_id": session.id,
        "role": session.role,
        "candidate_name": session.candidate_name,
        "extracted_skills": loads(session.extracted_skills_json, []),
        "turns": [
            {
                "turn_number": turn.turn_number,
                "question": turn.question,
                "answer": turn.answer,
                "difficulty": turn.difficulty,
                "answer_score": loads(turn.answer_score_json, {}),
                "generation_trace": loads(turn.generation_trace_json, {}),
            }
            for turn in session.turns
        ],
        "summary": summary,
    }


def available_roles() -> list[dict]:
    return ROLE_OPTIONS
