import re
from io import BytesIO

from fastapi import UploadFile
from pypdf import PdfReader

from app.services.embeddings import tokenize


SKILL_LEXICON = {
    "python",
    "fastapi",
    "flask",
    "django",
    "sql",
    "sqlite",
    "postgresql",
    "mongodb",
    "react",
    "next.js",
    "node.js",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "machine learning",
    "deep learning",
    "nlp",
    "computer vision",
    "pytorch",
    "tensorflow",
    "scikit-learn",
    "pandas",
    "numpy",
    "rag",
    "llm",
    "embeddings",
    "vector database",
    "api",
    "microservices",
    "redis",
    "celery",
    "git",
    "ci/cd",
}

DOMAIN_HINTS = {
    "backend": ["api", "fastapi", "flask", "django", "microservices", "database", "redis"],
    "ai_ml": ["machine learning", "deep learning", "nlp", "computer vision", "pytorch", "tensorflow"],
    "data_science": ["pandas", "numpy", "analytics", "visualization", "statistics", "regression"],
    "cloud_devops": ["docker", "kubernetes", "aws", "gcp", "azure", "ci/cd"],
}


async def extract_resume_text(file: UploadFile) -> str:
    raw = await file.read()
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()

    if filename.endswith(".pdf") or "pdf" in content_type:
        reader = PdfReader(BytesIO(raw))
        pages = [(page.extract_text() or "") for page in reader.pages]
        text = "\n".join(pages)
    else:
        text = raw.decode("utf-8", errors="ignore")

    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        raise ValueError("The uploaded resume did not contain readable text.")
    return cleaned


def infer_candidate_name(resume_text: str) -> str | None:
    lines = [line.strip() for line in re.split(r"[\n\r]+| {3,}", resume_text) if line.strip()]
    if not lines:
        return None
    first = lines[0][:80]
    if "@" in first or len(first.split()) > 5:
        return None
    return first


def extract_skills(resume_text: str) -> list[str]:
    lowered = resume_text.lower()
    found = {skill for skill in SKILL_LEXICON if skill in lowered}

    token_set = set(tokenize(resume_text))
    aliases = {
        "sklearn": "scikit-learn",
        "postgres": "postgresql",
        "k8s": "kubernetes",
        "tf": "tensorflow",
    }
    for alias, normalized in aliases.items():
        if alias in token_set:
            found.add(normalized)

    return sorted(found)


def infer_domains(skills: list[str], resume_text: str) -> list[str]:
    lowered = resume_text.lower()
    skill_set = set(skills)
    domains: list[str] = []
    for domain, hints in DOMAIN_HINTS.items():
        matches = sum(1 for hint in hints if hint in lowered or hint in skill_set)
        if matches:
            domains.append(domain)
    return domains
