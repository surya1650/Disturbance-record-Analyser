"""Load and query the normalized standards context shipped with dr-analyser."""
from __future__ import annotations

from importlib.resources import files
from typing import Any, Iterable

import yaml


def _load_yaml(name: str) -> dict[str, Any]:
    resource = files(__package__).joinpath(name)
    with resource.open("r", encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"invalid standards resource: {name}")
    return value


def load_sources() -> list[dict[str, Any]]:
    """Return the immutable source-document manifest."""
    return list(_load_yaml("sources.yaml").get("sources", []))


def load_catalogue() -> list[dict[str, Any]]:
    """Return every normalized standards chunk."""
    return list(_load_yaml("catalogue.yaml").get("chunks", []))


def search_chunks(*, asset_type: str | None = None, topic: str | None = None,
                  source_id: str | None = None, active_only: bool = False
                  ) -> list[dict[str, Any]]:
    """Find chunks by source, asset type, or topic.

    Matching is case-insensitive. An ``all`` asset tag applies to every asset.
    Topic matching accepts either an exact tag or a substring of a tag.
    """
    asset = asset_type.casefold() if asset_type else None
    topic_key = topic.casefold() if topic else None
    found: list[dict[str, Any]] = []
    for chunk in load_catalogue():
        assets = {str(item).casefold() for item in chunk.get("asset_types", [])}
        topics = [str(item).casefold() for item in chunk.get("topics", [])]
        if asset and asset not in assets and "all" not in assets:
            continue
        if topic_key and not any(topic_key in item for item in topics):
            continue
        if source_id and chunk.get("source_id") != source_id:
            continue
        if active_only and chunk.get("analyzer_state") != "active":
            continue
        found.append(chunk)
    return found


def context_text(chunks: Iterable[dict[str, Any]]) -> str:
    """Render chunks as compact, retrieval-friendly text."""
    lines: list[str] = []
    for chunk in chunks:
        lines.append(
            f"[{chunk['id']}] {chunk['source_id']} {chunk['locator']} "
            f"({chunk['analyzer_state']})"
        )
        lines.append(str(chunk.get("summary", "")))
        for rule in chunk.get("rules", []):
            lines.append(f"- {rule}")
    return "\n".join(lines)
