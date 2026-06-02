from pydantic import BaseModel, Field


class RoleOption(BaseModel):
    id: str
    label: str
    description: str


class RetrievedContext(BaseModel):
    chunk_id: int
    role: str
    source_title: str
    source_url: str | None = None
    score: float
    text: str


class QuestionPayload(BaseModel):
    turn_number: int
    question: str
    difficulty: str
    retrieved_context: list[RetrievedContext]
    generation_trace: dict


class SessionResponse(BaseModel):
    session_id: str
    role: str
    candidate_name: str | None
    extracted_skills: list[str]
    domains: list[str]
    topics: list[str]
    status: str
    current_question: QuestionPayload | None


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=2, max_length=6000)


class AnswerResponse(BaseModel):
    session_id: str
    status: str
    answer_score: dict
    next_question: QuestionPayload | None
    summary: dict | None = None


class SessionSummary(BaseModel):
    session_id: str
    role: str
    candidate_name: str | None
    extracted_skills: list[str]
    turns: list[dict]
    summary: dict
