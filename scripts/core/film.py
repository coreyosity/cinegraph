"""The `Film` schema — the single data shape the analytics operate on.

Deliberately source-agnostic: `from_note()` builds one from an Obsidian note's
frontmatter dict today; a database row could build one tomorrow. List fields are
normalized once here (scalar-or-list-or-None → list), so the analytics never re-normalize.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .text import as_list


@dataclass
class Film:
    tmdb_id: int | None = None
    title: str | None = None
    year: int | None = None
    rating: float | None = None          # the user's rating (None if unrated)
    runtime: int | None = None
    director: str | None = None
    cast: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    studios: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)   # raw TMDB keywords (pre-stoplist)
    country: str | None = None
    country_code: str | None = None
    language: str | None = None
    watched: str | None = None
    poster: str | None = None
    url: str | None = None               # site slug, if known (filled by the adapter)

    @classmethod
    def from_note(cls, meta: dict) -> Film:
        """Build a Film from a note's frontmatter dict."""
        rating = meta.get("rating")
        return cls(
            tmdb_id=meta.get("tmdb_id"),
            title=meta.get("title"),
            year=meta.get("year"),
            rating=float(rating) if isinstance(rating, (int, float)) else None,
            runtime=meta.get("runtime"),
            director=meta.get("director") or None,
            cast=as_list(meta.get("cast")),
            genres=as_list(meta.get("genres")),
            studios=as_list(meta.get("studios")),
            keywords=as_list(meta.get("keywords")),
            country=meta.get("country"),
            country_code=meta.get("country_code"),
            language=meta.get("language"),
            watched=meta.get("watched"),
            poster=meta.get("poster"),
            url=meta.get("url"),
        )
