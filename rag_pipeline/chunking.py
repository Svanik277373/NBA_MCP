"""Paragraph-aware chunking targeting ~300-500 tokens per chunk with overlap.

Token counts are approximated from word counts (~0.75 words/token is a
reasonable average for English prose) rather than pulling in a tokenizer
library — precise token counts don't matter for chunk-size tuning, only
consistency, and this keeps the dependency list smaller.
"""

from __future__ import annotations

# ~425 tokens ≈ 320 words at the 0.75 words/token approximation — the
# midpoint of the requested 300-500 token range.
TARGET_WORDS = 320
OVERLAP_WORDS = 45


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def chunk_text(
    text: str,
    target_words: int = TARGET_WORDS,
    overlap_words: int = OVERLAP_WORDS,
) -> list[str]:
    """Chunk text into paragraph-aligned windows of ~target_words, with the
    last overlap_words words of each chunk repeated at the start of the
    next chunk so retrieval doesn't lose context at a chunk boundary.
    """
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[str] = []
    current_paragraphs: list[str] = []
    current_word_count = 0

    def flush() -> list[str]:
        """Finalize current_paragraphs into a chunk; return the overlap
        paragraphs (as words) to seed the next chunk."""
        chunk_text_ = "\n\n".join(current_paragraphs)
        chunks.append(chunk_text_)
        overlap_words_list = chunk_text_.split()[-overlap_words:]
        return overlap_words_list

    for paragraph in paragraphs:
        paragraph_words = paragraph.split()

        # A single oversized paragraph: emit whatever's accumulated so far,
        # then hard-split the paragraph itself by word count.
        if len(paragraph_words) > target_words * 1.5:
            if current_paragraphs:
                flush()
                current_paragraphs = []
                current_word_count = 0
            for i in range(0, len(paragraph_words), target_words):
                chunks.append(" ".join(paragraph_words[i : i + target_words]))
            continue

        if current_word_count + len(paragraph_words) > target_words and current_paragraphs:
            overlap = flush()
            current_paragraphs = [" ".join(overlap)] if overlap else []
            current_word_count = len(overlap)

        current_paragraphs.append(paragraph)
        current_word_count += len(paragraph_words)

    if current_paragraphs:
        chunks.append("\n\n".join(current_paragraphs))

    return chunks
