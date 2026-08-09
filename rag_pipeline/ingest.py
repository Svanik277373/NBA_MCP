"""Ingest the scouting corpus into Chroma.

Walks corpus/**/*.md, parses frontmatter, chunks each doc's body (~300-500
tokens, with overlap), embeds every chunk with Voyage, and upserts into the
Chroma collection. Re-running this script is safe — the collection is
dropped and recreated each time rather than appended to, which avoids stale
or duplicate chunks when a corpus file is edited or removed. For a corpus
this size that's cheap; a larger corpus would want incremental upserts
keyed by a content hash instead.

Usage:
    python -m rag_pipeline.ingest
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from rag_pipeline.chunking import chunk_text
from rag_pipeline.embeddings import embed_documents
from rag_pipeline.frontmatter import parse_frontmatter
from rag_pipeline.vectorstore import reset_collection

CORPUS_DIR = Path(__file__).parent.parent / "corpus"
EMBED_BATCH_SIZE = 128


def _clean_metadata(raw: dict, extra: dict) -> dict:
    """Chroma metadata values must be str/int/float/bool — drop Nones and
    merge in the chunk-level fields (source_file, chunk_index)."""
    merged = {**raw, **extra}
    return {k: v for k, v in merged.items() if v is not None}


def load_and_chunk_corpus() -> tuple[list[str], list[str], list[dict]]:
    """Returns (ids, documents, metadatas) for every chunk across the corpus."""
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    md_files = sorted(CORPUS_DIR.rglob("*.md"))
    for file_path in md_files:
        raw_text = file_path.read_text(encoding="utf-8")
        parsed = parse_frontmatter(raw_text)
        rel_path = file_path.relative_to(CORPUS_DIR).as_posix()

        chunks = chunk_text(parsed.body)
        for i, chunk in enumerate(chunks):
            ids.append(f"{rel_path}::chunk{i}")
            documents.append(chunk)
            metadatas.append(
                _clean_metadata(
                    parsed.metadata,
                    {"source_file": rel_path, "chunk_index": i},
                )
            )

    return ids, documents, metadatas


def ingest() -> None:
    load_dotenv()

    ids, documents, metadatas = load_and_chunk_corpus()
    if not ids:
        print(f"No markdown files found under {CORPUS_DIR}")
        return

    print(f"Found {len(documents)} chunks across corpus files.")

    all_embeddings: list[list[float]] = []
    for i in range(0, len(documents), EMBED_BATCH_SIZE):
        batch = documents[i : i + EMBED_BATCH_SIZE]
        all_embeddings.extend(embed_documents(batch))
        print(f"  embedded {min(i + EMBED_BATCH_SIZE, len(documents))}/{len(documents)}")

    collection = reset_collection()
    collection.add(ids=ids, documents=documents, embeddings=all_embeddings, metadatas=metadatas)

    print(f"Ingested {collection.count()} chunks into Chroma collection '{collection.name}'.")


if __name__ == "__main__":
    ingest()
