import json
import sqlite3
from pathlib import Path

from app.core.config import get_settings
from app.services.embeddings import cosine_similarity, embed_text, tokenize


class VectorStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or get_settings().resolved_vector_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    source_title TEXT NOT NULL,
                    source_url TEXT,
                    source_tag TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    UNIQUE(source_title, source_tag, chunk_index)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_role ON knowledge_chunks(role)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_tag ON knowledge_chunks(source_tag)")

    def count_chunks(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM knowledge_chunks").fetchone()
            return int(row["total"])

    def upsert_chunk(
        self,
        *,
        role: str,
        source_title: str,
        source_url: str | None,
        source_tag: str,
        chunk_index: int,
        text: str,
    ) -> None:
        embedding = embed_text(text)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_chunks
                    (role, source_title, source_url, source_tag, chunk_index, text, embedding, token_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_title, source_tag, chunk_index) DO UPDATE SET
                    role=excluded.role,
                    source_url=excluded.source_url,
                    text=excluded.text,
                    embedding=excluded.embedding,
                    token_count=excluded.token_count
                """,
                (
                    role,
                    source_title,
                    source_url,
                    source_tag,
                    chunk_index,
                    text,
                    json.dumps(embedding),
                    len(tokenize(text)),
                ),
            )

    def search(self, query: str, role: str, source_tags: list[str], top_k: int = 4) -> list[dict]:
        query_embedding = embed_text(query)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM knowledge_chunks
                WHERE role = ? OR source_tag IN ({})
                """.format(",".join("?" for _ in source_tags) or "''"),
                [role, *source_tags],
            ).fetchall()

        scored = []
        seen_text = set()
        for row in rows:
            score = cosine_similarity(query_embedding, json.loads(row["embedding"]))
            if row["text"] in seen_text:
                continue
            seen_text.add(row["text"])
            scored.append(
                {
                    "chunk_id": row["id"],
                    "role": row["role"],
                    "source_title": row["source_title"],
                    "source_url": row["source_url"],
                    "source_tag": row["source_tag"],
                    "text": row["text"],
                    "score": round(float(score), 4),
                }
            )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]
