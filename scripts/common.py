"""Shared helpers for the cinegraph pipeline.

Notes are plain Markdown with a YAML frontmatter block. We deliberately keep the
frontmatter as *plain-text* properties (queryable by Obsidian Bases) and put the
[[wikilinks]] in the note **body** (so they resolve in both Obsidian and Quartz's
graph). See the plan for why frontmatter links don't work in either tool.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

import yaml

# The pure text helpers now live in core (vault-free). Re-exported here so existing
# `common.canonical` / `common.theme_keywords` call-sites keep working unchanged.
from core.film import Film
from core.text import KEYWORD_STOP, as_list, canonical, theme_keywords  # noqa: F401

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)

# Project config (thresholds etc.) lives in cinegraph.yaml at the repo root. These
# defaults apply when the file (or any key) is absent, so the pipeline runs the same
# with or without it.
_DEFAULT_CONFIG = {
    "graph": {
        # Entities linking fewer films than this are hidden from BOTH graphs (see
        # gen_entities). 1 = never hide that type.
        "min_films": {"people": 2, "studios": 2, "genres": 1},
        # People with any of these roles are never hidden, whatever their film count.
        "always_show_roles": ["director"],
    },
    "themes": {
        # A TMDB keyword becomes a browsable Theme page once it tags this many films.
        "min_films": 5,
    },
}

def _deep_merge(base: dict, over: dict) -> dict:
    """Recursively merge `over` into `base` (in place); returns `base`."""
    for key, value in (over or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(vault: Path) -> dict:
    """Load `cinegraph.yaml` (looked for next to the vault, i.e. the repo root),
    deep-merged over the built-in defaults. Missing file or keys → defaults."""
    cfg = copy.deepcopy(_DEFAULT_CONFIG)
    path = Path(vault).resolve().parent / "cinegraph.yaml"
    if path.exists():
        user = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(user, dict):
            _deep_merge(cfg, user)
    return cfg

# Characters that are unsafe in filenames on common filesystems. We keep spaces and
# most punctuation (Obsidian/Quartz handle them) but strip path/reserved chars so a
# wikilink target maps cleanly to one file.
_UNSAFE_FILENAME = re.compile(r'[\\/:*?"<>|#^\[\]]')


def read_note(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) for a note. Missing frontmatter -> ({}, text)."""
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, match.group(2)


def dump_note(meta: dict, body: str) -> str:
    """Serialize a note back to text with a YAML frontmatter block."""
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).rstrip("\n")
    body = body.lstrip("\n")
    return f"---\n{fm}\n---\n\n{body}\n" if body else f"---\n{fm}\n---\n"


def write_note(path: Path, meta: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_note(meta, body), encoding="utf-8")


def link_name(name: str) -> str:
    """The single canonical identifier for an entity.

    Used *identically* as the note basename AND as the [[wikilink]] text in film
    bodies, so links resolve by literal basename match in both Obsidian and Quartz
    (Quartz is case-sensitive and does not normalize). Strips path/reserved chars and
    trailing dots/spaces (Windows-hostile), e.g. "Warner Bros." -> "Warner Bros".
    """
    cleaned = _UNSAFE_FILENAME.sub("", canonical(name))
    # Re-collapse whitespace: stripping a separator like " / " leaves a double space.
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or "untitled"


def wikilink(name: str) -> str:
    """Render a body wikilink whose text equals the target note's basename."""
    return f"[[{link_name(name)}]]"


def iter_folder_notes(vault: Path, folder: str):
    """Yield (path, meta, body) for every note directly under <vault>/<folder>."""
    for path in sorted((vault / folder).glob("*.md")):
        meta, body = read_note(path)
        yield path, meta, body


def iter_film_notes(vault: Path):
    """Yield (path, meta, body) for every film note under <vault>/Films."""
    yield from iter_folder_notes(vault, "Films")


def load_films(vault: Path, folder: str = "Films") -> list[Film]:
    """Vault adapter: read a folder of notes into `core.Film` objects for the analytics."""
    return [Film.from_note(meta) for _p, meta, _b in iter_folder_notes(vault, folder)]


# Wikilink targets referenced anywhere in a note body, e.g. [[Denis Villeneuve]].
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\]")


def body_link_targets(body: str) -> set[str]:
    # Literal (only trim ends) — Quartz resolves links by exact basename, so the
    # verifier must too, rather than canonicalizing away real drift.
    return {m.strip() for m in _WIKILINK_RE.findall(body)}
