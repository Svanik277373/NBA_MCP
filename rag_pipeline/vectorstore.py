"""Chroma persistent vector store wrapper.

Embeddings are computed externally via Voyage (rag_pipeline.embeddings) and
passed in explicitly — Chroma's built-in embedding functions are not used,
so there's exactly one place (embeddings.py) that talks to an embedding API.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

_PERSIST_DIR = Path(__file__).parent / os.environ.get("CHROMA_PERSIST_DIR", "./chroma_db")
_COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION_NAME", "nba_scouting")

_client: chromadb.ClientAPI | None = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(_PERSIST_DIR))
    return _client


def get_collection() -> Collection:
    return _get_client().get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def reset_collection() -> Collection:
    """Drop and recreate the collection — used by ingest.py so re-running
    ingestion is idempotent instead of accumulating duplicate/stale chunks.
    """
    client = _get_client()
    try:
        client.delete_collection(_COLLECTION_NAME)
    except Exception:
        pass  # collection didn't exist yet — fine
    return get_collection()


def add_chunks(
    ids: list[str],
    documents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
) -> None:
    if not ids:
        return
    get_collection().add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)


def query(
    query_embedding: list[float],
    top_k: int = 5,
    where: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Top-k similarity search. `where` is a Chroma metadata filter, e.g.
    {"player": "Anthony Edwards"} — applied before the vector search so it
    narrows the candidate set rather than post-filtering results.
    """
    return get_collection().query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
    )


def get_by_metadata(where: dict[str, Any], limit: int | None = None) -> dict[str, Any]:
    """Direct metadata lookup — no embedding/similarity search involved.
    Used when we already know exactly which doc we want (e.g. a player's
    own profile, to use its text as a style-similarity query).
    """
    return get_collection().get(where=where, limit=limit)


def count() -> int:
    return get_collection().count()
