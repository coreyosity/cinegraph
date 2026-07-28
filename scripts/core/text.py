"""Pure text/normalization helpers shared by the analytics. No I/O, no vault, no yaml."""

from __future__ import annotations

import re

# TMDB "keywords" that are production/credits metadata, not themes. Excluded from Theme
# pages *and* from the film-similarity scoring (they'd falsely link unrelated films).
KEYWORD_STOP = {
    "duringcreditsstinger", "aftercreditsstinger", "post-credits scene",
    "mid-credits scene", "woman director", "3d",
}


def canonical(name: str) -> str:
    """Collapse whitespace. The result is used verbatim as both the wikilink text
    and the note basename, so links stay case-exact (Quartz is case-sensitive)."""
    return re.sub(r"\s+", " ", str(name)).strip()


def as_list(value) -> list:
    """Normalize a frontmatter field that may be a scalar, list, or None to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if v not in (None, "")]
    return [value]


def theme_keywords(keywords) -> list[str]:
    """Keywords with the non-thematic stop-list removed, canonicalized."""
    return [canonical(k) for k in as_list(keywords) if canonical(k).lower() not in KEYWORD_STOP]
