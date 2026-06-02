import json
import re
from collections import Counter

from app.services.embeddings import tokenize
from app.services.role_profiles import ROLE_QUERY_HINTS, ROLE_TO_SOURCE_TAGS
from app.services.vector_store import VectorStore


def build_topics(role: str, skills: list[str], domains: list[str]) -> list[str]:
    role_hints = " ".join(ROLE_QUERY_HINTS.get(role, []))
    signals = skills + domains + tokenize(role_hints)
    counts = Counter(token for token in signals if len(token) > 3)
    topics = [topic for topic, _ in counts.most_common(8)]
    return topics or ["fundamentals", "system design", "evaluation"]


def construct_query(role: str, resume_text: str, skills: list[str], domains: list[str], previous_answer: str | None = None) -> str:
    resume_terms = " ".join(skills[:10] + domains[:5])
    role_terms = " ".join(ROLE_QUERY_HINTS.get(role, []))
    answer_terms = f" candidate response: {previous_answer[:700]}" if previous_answer else ""
    return f"role: {role}. resume skills/domains: {resume_terms}. role expectations: {role_terms}.{answer_terms}"


def retrieve_context(
    role: str,
    resume_text: str,
    skills: list[str],
    domains: list[str],
    previous_answer: str | None = None,
    top_k: int = 4,
) -> tuple[str, list[dict]]:
    query = construct_query(role, resume_text, skills, domains, previous_answer)
    source_tags = ROLE_TO_SOURCE_TAGS.get(role, [])
    chunks = VectorStore().search(query=query, role=role, source_tags=source_tags, top_k=top_k)
    return query, chunks


def _keyword_candidates(text: str) -> list[str]:
    concept_order = [
        "bias",
        "variance",
        "regularization",
        "cross-validation",
        "overfitting",
        "supervised learning",
        "unsupervised learning",
        "model evaluation",
        "data leakage",
        "precision",
        "recall",
        "decision trees",
        "neural networks",
        "nearest neighbors",
        "feature engineering",
        "vector search",
        "embeddings",
        "chunking",
        "session continuity",
        "persistence",
        "api design",
        "validation",
    ]
    lowered = text.lower()
    concepts = [concept for concept in concept_order if concept in lowered]
    stop = {
        "that",
        "with",
        "from",
        "this",
        "have",
        "will",
        "model",
        "learning",
        "data",
        "using",
        "when",
        "would",
        "should",
        "system",
        "machine",
        "performance",
        "examples",
        "example",
        "source",
        "measure",
        "training",
        "experience",
    }
    counts = Counter(token for token in tokenize(text) if len(token) > 4 and token not in stop)
    fallback = [word for word, _ in counts.most_common(10)]
    return list(dict.fromkeys([*concepts, *fallback]))[:10]


def choose_difficulty(skills: list[str], domains: list[str], turn_number: int) -> str:
    advanced_signals = {"pytorch", "tensorflow", "rag", "embeddings", "kubernetes", "microservices", "deep learning"}
    score = len(advanced_signals.intersection(set(skills))) + len(domains)
    if turn_number >= 4 or score >= 5:
        return "advanced"
    if turn_number >= 2 or score >= 2:
        return "intermediate"
    return "foundational"


def generate_question(
    *,
    role: str,
    role_label: str,
    turn_number: int,
    skills: list[str],
    domains: list[str],
    retrieved_context: list[dict],
    previous_answer: str | None = None,
) -> tuple[str, dict, str]:
    context_text = " ".join(chunk["text"] for chunk in retrieved_context)
    keywords = _keyword_candidates(context_text)
    difficulty = choose_difficulty(skills, domains, turn_number)
    skill_phrase = ", ".join(skills[:4]) if skills else "your resume background"
    focus = keywords[turn_number % len(keywords)] if keywords else "model evaluation"
    supporting = keywords[(turn_number + 2) % len(keywords)] if len(keywords) > 2 else "tradeoffs"
    article = "an" if role_label[:1].lower() in {"a", "e", "i", "o", "u"} else "a"

    if previous_answer:
        prompt = (
            f"As {article} {role_label}, build on your previous answer and explain how you would apply "
            f"{focus} and {supporting} in a real project connected to {skill_phrase}. "
            "What assumptions would you validate, and what failure mode would you watch for?"
        )
    elif difficulty == "foundational":
        prompt = (
            f"For the {role_label} role, explain {focus} using an example from {skill_phrase}. "
            f"How does the retrieved material connect {focus} with {supporting}?"
        )
    elif difficulty == "intermediate":
        prompt = (
            f"Suppose you are designing a solution for the {role_label} role. "
            f"Use {focus} and {supporting} to decide between two implementation approaches, "
            f"and connect your reasoning to {skill_phrase}."
        )
    else:
        prompt = (
            f"Design a production-grade approach for the {role_label} role where {focus} is central. "
            f"Discuss the mathematical or architectural tradeoff involving {supporting}, "
            "then describe how you would test whether your choice generalizes."
        )

    trace = {
        "role": role,
        "candidate_signals": {"skills": skills, "domains": domains},
        "context_chunk_ids": [chunk["chunk_id"] for chunk in retrieved_context],
        "source_titles": sorted({chunk["source_title"] for chunk in retrieved_context}),
        "keywords": keywords[:8],
        "question_policy": "role + resume signals + retrieved chunk keywords + turn difficulty",
    }
    return prompt, trace, difficulty


def score_answer(answer: str, retrieved_context: list[dict]) -> dict:
    answer_terms = set(tokenize(answer))
    context_terms = set(tokenize(" ".join(chunk["text"] for chunk in retrieved_context)))
    overlap = sorted(answer_terms.intersection(context_terms))
    concept_coverage = min(1.0, len(overlap) / 18)
    specificity = min(1.0, len(answer_terms) / 80)
    score = round((0.65 * concept_coverage + 0.35 * specificity) * 100, 1)
    return {
        "score": score,
        "concept_coverage": round(concept_coverage, 2),
        "specificity": round(specificity, 2),
        "matched_terms": overlap[:12],
        "feedback": _feedback(score),
    }


def _feedback(score: float) -> str:
    if score >= 75:
        return "Strong answer: it connected multiple retrieved concepts with enough detail."
    if score >= 45:
        return "Good direction: add clearer tradeoffs, assumptions, and implementation detail."
    return "Needs depth: anchor the answer in the retrieved concepts and give a concrete example."


def dumps(data: object) -> str:
    return json.dumps(data, ensure_ascii=True)


def loads(raw: str | None, fallback: object) -> object:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback
