"""Minimal flat-key frontmatter parser for the scouting corpus.

Deliberately not using a YAML library: the corpus format spec (see
README) only needs flat `key: value` pairs, so a hand-rolled parser keeps
one fewer dependency for a feature this small.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedDoc:
    metadata: dict[str, str | bool]
    body: str


def parse_frontmatter(raw_text: str) -> ParsedDoc:
    """Split a corpus markdown file into (metadata, body).

    Expected format:

        ---
        title: Some Title
        doc_type: player_profile
        player: Anthony Edwards
        team: MIN
        date: 2024-11-15
        historical: true
        ---

        # Body starts here...

    Missing frontmatter is not an error — the whole file is treated as body
    with empty metadata, so plain notes still ingest.
    """
    text = raw_text.strip("\n")
    if not text.startswith("---"):
        return ParsedDoc(metadata={}, body=raw_text.strip())

    lines = text.split("\n")
    # lines[0] == "---"; find the closing delimiter
    try:
        close_idx = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        # Opened with --- but never closed — treat as body, not metadata.
        return ParsedDoc(metadata={}, body=raw_text.strip())

    metadata: dict[str, str | bool] = {}
    for line in lines[1:close_idx]:
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.lower() in ("true", "false"):
            metadata[key] = value.lower() == "true"
        else:
            metadata[key] = value

    body = "\n".join(lines[close_idx + 1 :]).strip()
    return ParsedDoc(metadata=metadata, body=body)
