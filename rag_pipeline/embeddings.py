"""Embedding client wrapper — pluggable between a local model and Voyage.

Two backends, selected via EMBEDDING_PROVIDER:

- "local" (default): all-MiniLM-L6-v2 via Chroma's bundled ONNX runtime.
  Runs fully offline after the model is cached on first use (~90MB
  download), no API key, no rate limits, no per-call cost — the right
  default for a demo/dev corpus this size.
- "voyage": Voyage AI's hosted embeddings (voyage-3-lite by default).
  Better retrieval quality on larger/harder corpora, but needs
  VOYAGE_API_KEY and is subject to Voyage's rate limits.

Both paths expose the same embed_documents/embed_query interface so
nothing downstream (ingest.py, retrieval) needs to know which is active.
"""

from __future__ import annotations

import os

EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "local")
VOYAGE_MODEL = os.environ.get("VOYAGE_EMBED_MODEL", "voyage-3-lite")

_local_ef = None
_voyage_client = None


def _get_local_ef():
    global _local_ef
    if _local_ef is None:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        _local_ef = ONNXMiniLM_L6_V2()
    return _local_ef


def _get_voyage_client():
    global _voyage_client
    if _voyage_client is None:
        import voyageai

        _voyage_client = voyageai.Client()  # reads VOYAGE_API_KEY from env
    return _voyage_client


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of corpus chunks for indexing."""
    if not texts:
        return []
    if EMBEDDING_PROVIDER == "voyage":
        result = _get_voyage_client().embed(texts, model=VOYAGE_MODEL, input_type="document")
        return result.embeddings
    return [vec.tolist() for vec in _get_local_ef()(texts)]


def embed_query(text: str) -> list[float]:
    """Embed a single search query.

    Voyage distinguishes query vs. document embeddings for better retrieval
    (input_type="query"); the local MiniLM model has no such distinction.
    """
    if EMBEDDING_PROVIDER == "voyage":
        result = _get_voyage_client().embed([text], model=VOYAGE_MODEL, input_type="query")
        return result.embeddings[0]
    return _get_local_ef()([text])[0].tolist()
