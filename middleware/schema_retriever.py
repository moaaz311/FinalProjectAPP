"""
schema_retriever.py
-------------------
Replaces the "load entire schema.txt" pattern with targeted, keyword-driven
schema grounding.

This module:
  1. Parses the structured schema.json once at startup.
  2. On every request, extracts ONLY the views relevant to the question.
  3. Serialises those views into a tight, token-efficient prompt block.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────
# 1. Load schema once at module import
# ──────────────────────────────────────────────

_SCHEMA_PATH = Path(__file__).parent.parent / "knowledge" / "schema.json"

with _SCHEMA_PATH.open(encoding="utf-8") as _f:
    _SCHEMA: dict[str, Any] = json.load(_f)

# Build lookup: view_name → view_dict
_VIEW_INDEX: dict[str, dict] = {v["view"]: v for v in _SCHEMA["views"]}

# keyword → [view_names]
_KEYWORD_HINTS: dict[str, list[str]] = _SCHEMA["keyword_hints"]


# ──────────────────────────────────────────────
# 2. Keyword extraction
# ──────────────────────────────────────────────

def _extract_keywords(question: str) -> list[str]:
    """Return all keyword_hints keys found in the lowercased question."""
    q = question.lower()
    return [kw for kw in _KEYWORD_HINTS if kw in q]


# ──────────────────────────────────────────────
# 3. Relevant view resolution
# ──────────────────────────────────────────────

def get_relevant_views(question: str) -> list[dict]:
    """
    Return deduplicated view dicts that are relevant to the question.

    Strategy:
      1. Keyword matching against keyword_hints map.
      2. If no keywords match, fall back to trade domain.
    """
    matched_keywords = _extract_keywords(question)
    view_names: list[str] = []

    for kw in matched_keywords:
        for vname in _KEYWORD_HINTS[kw]:
            if vname not in view_names:
                view_names.append(vname)

    if not view_names:
        view_names = _SCHEMA["domain_routing"]["trade"]

    views = []
    for vname in view_names:
        if vname in _VIEW_INDEX:
            views.append(_VIEW_INDEX[vname])

    return views


# ──────────────────────────────────────────────
# 4. Prompt-ready schema serialisation
# ──────────────────────────────────────────────

def build_schema_block(views: list[dict]) -> str:
    """Convert a list of view dicts into a compact, LLM-readable schema block."""
    lines: list[str] = []
    lines.append(f"DATABASE: {_SCHEMA['database']}")
    lines.append("")

    for v in views:
        lines.append(f"VIEW: {v['view']}")
        lines.append(f"DESC: {v.get('description', '')}")
        lines.append("COLUMNS:")

        for col in v.get("columns", []):
            note = f"  — {col['notes']}" if col.get("notes") else ""
            lines.append(
                f"  {col['name']:<30} {col['type']:<10} {col['role']}{note}"
            )

        if v.get("relationships"):
            lines.append("JOINS:")
            for rel in v["relationships"]:
                lines.append(f"  {rel['fk']}  →  {rel['references']}")

        if v.get("kpis"):
            lines.append("KPIS (business definitions):")
            for name, defn in v["kpis"].items():
                lines.append(f"  {name} = {defn}")

        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 5. Validation helpers
# ──────────────────────────────────────────────

def get_all_valid_views() -> set[str]:
    """All view names defined in the schema."""
    return set(_VIEW_INDEX.keys())


def get_valid_columns(view_name: str) -> set[str]:
    """All column names for a given view, or empty set if view not found."""
    v = _VIEW_INDEX.get(view_name)

    if not v:
        return set()

    return {col["name"] for col in v.get("columns", [])}


def get_all_valid_columns() -> set[str]:
    """Flat set of every column name across all views."""
    cols: set[str] = set()

    for v in _SCHEMA["views"]:
        for col in v.get("columns", []):
            cols.add(col["name"])

    return cols
