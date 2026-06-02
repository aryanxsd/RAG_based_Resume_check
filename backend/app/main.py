from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db import init_database


settings = get_settings()

app = FastAPI(
    title="Role-Based Candidate Screening RAG API",
    description="AI/ML and backend intern assignment API for resume-aware technical interviews.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_database()


app.include_router(router, prefix="/api")
