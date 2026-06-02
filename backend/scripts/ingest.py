import argparse
import json
import sys
import urllib.request
from urllib.error import URLError
from pathlib import Path

from pypdf import PdfReader

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services.chunking import split_into_chunks  # noqa: E402
from app.services.vector_store import VectorStore  # noqa: E402


def read_pdf(path: Path, max_pages: int | None = None) -> str:
    reader = PdfReader(str(path))
    pages = reader.pages[:max_pages] if max_pages else reader.pages
    return "\n".join(page.extract_text() or "" for page in pages)


def download_pdf(url: str, destination: Path, timeout: int) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        destination.write_bytes(response.read())
    return destination


def ingest_text(store: VectorStore, *, role: str, source_tag: str, source_title: str, source_url: str | None, text: str) -> int:
    chunks = split_into_chunks(text)
    for index, chunk in enumerate(chunks):
        store.upsert_chunk(
            role=role,
            source_title=source_title,
            source_url=source_url,
            source_tag=source_tag,
            chunk_index=index,
            text=chunk,
        )
    return len(chunks)


def ingest_seed_corpus(store: VectorStore) -> int:
    seed_dir = ROOT_DIR / "backend" / "data" / "seed_corpus"
    total = 0
    total += ingest_text(
        store,
        role="backend_engineer",
        source_tag="backend_ai_systems",
        source_title="Backend AI Systems Design Corpus",
        source_url=None,
        text=(seed_dir / "backend_ai_systems.txt").read_text(encoding="utf-8"),
    )
    foundations = (seed_dir / "ml_foundations.txt").read_text(encoding="utf-8")
    for role, tag in [
        ("ai_ml_engineer", "ai_ml"),
        ("data_science_applied_ml", "data_science"),
        ("advanced_theoretical_ml", "advanced_ml"),
    ]:
        total += ingest_text(
            store,
            role=role,
            source_tag=tag,
            source_title="Machine Learning Foundations Seed Corpus",
            source_url=None,
            text=foundations,
        )
    return total


def ingest_downloaded_sources(store: VectorStore, max_pages: int | None, only_first: int | None) -> int:
    settings = get_settings()
    sources_path = ROOT_DIR / "backend" / "data" / "knowledge_sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    if only_first:
        sources = sources[:only_first]

    total = 0
    for source in sources:
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in source["title"].lower())[:80]
        pdf_path = ROOT_DIR / "backend" / "data" / "raw" / f"{safe_name}.pdf"
        try:
            print(f"Downloading/reading {source['title']}", flush=True)
            download_pdf(source["url"], pdf_path, timeout=settings.pdf_download_timeout)
            text = read_pdf(pdf_path, max_pages=max_pages)
            total += ingest_text(
                store,
                role=source["role"],
                source_tag=source["source_tag"],
                source_title=source["title"],
                source_url=source["url"],
                text=text,
            )
        except (OSError, URLError) as exc:
            print(f"Skipped {source['title']}: {exc}", flush=True)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the role-specific RAG vector database.")
    parser.add_argument("--download-books", action="store_true", help="Download and ingest assignment book PDFs.")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional page limit per downloaded book.")
    parser.add_argument("--only-first", type=int, default=None, help="Only ingest the first N configured book sources.")
    args = parser.parse_args()

    store = VectorStore()
    total = ingest_seed_corpus(store)
    if args.download_books:
        total += ingest_downloaded_sources(store, max_pages=args.max_pages, only_first=args.only_first)
    print(f"Ingested/updated {total} chunks. Vector store now has {store.count_chunks()} chunks.")


if __name__ == "__main__":
    main()
