import re


def split_into_chunks(text: str, chunk_size: int = 900, overlap: int = 160) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) + 1 <= chunk_size:
            current = f"{current} {sentence}".strip()
            continue
        if current:
            chunks.append(current)
        if chunks and overlap > 0:
            current = f"{chunks[-1][-overlap:]} {sentence}".strip()
        else:
            current = sentence

    if current:
        chunks.append(current)
    return chunks
