"""Chunk 2 — TMDB enrichment.

Fills each film note with the metadata needed for analysis and the relationship graph:
genres, director, top cast, studios, keywords, runtime, poster. Resolution order for a
film's TMDB id:

    1. frontmatter `tmdb_id` (already enriched)
    2. `/search/movie` by title + year
    3. scrape the exact TMDB id + type off the film's Letterboxd page (the `letterboxd`
       URL in frontmatter) — recovers year-mismatches and TV titles that movie-search
       can't find.

Handles both `movie` and `tv` content (Letterboxd logs anthology TV like Black Mirror).
The body is regenerated with normalized `[[wikilinks]]` so gen_entities.py has resolvable
targets. Idempotent; never overwrites Letterboxd-owned `rating` / `watched`.

Needs a free TMDB v3 API key in env `TMDB_KEY` (or a `.env` at the project root).

Usage:
    python scripts/enrich.py --vault vault
    python scripts/enrich.py --vault vault --missing        # only unenriched films
    python scripts/enrich.py --vault vault --only "Parasite"
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import requests

import common

API = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
LB_TMDB_RE = re.compile(r"themoviedb\.org/(movie|tv)/(\d+)")
FILM_KEY_ORDER = [
    "type", "title", "year", "tmdb_id", "content_type", "rating", "watched", "runtime",
    "genres", "director", "studios", "cast", "keywords", "country", "country_code",
    "language", "poster", "tags",
]
PRESERVE = {"rating", "watched"}  # Letterboxd-owned; never overwritten
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load_key(cli_key: str | None) -> str:
    if cli_key:
        return cli_key
    if os.environ.get("TMDB_KEY"):
        return os.environ["TMDB_KEY"]
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("TMDB_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("No TMDB key. Set TMDB_KEY env var or add it to .env")


class TMDBError(RuntimeError):
    """Raised with a sanitized message (never includes the api_key)."""


def tmdb_get(session: requests.Session, path: str, key: str, **params) -> dict:
    params["api_key"] = key
    for attempt in range(4):
        resp = session.get(f"{API}/{path}", params=params, timeout=20)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            time.sleep(1.5 * (attempt + 1))
            continue
        raise TMDBError(f"TMDB {resp.status_code} for {path}")  # no key in message
    raise TMDBError(f"TMDB retries exhausted for {path}")


def search_movie(session, key, title, year) -> int | None:
    params = {"query": title}
    if year:
        params["primary_release_year"] = year
    results = tmdb_get(session, "search/movie", key, **params).get("results", [])
    return results[0]["id"] if results else None


def scrape_letterboxd(session, url) -> tuple[str | None, int | None]:
    """Return (content_type, tmdb_id) parsed off a Letterboxd film page, or (None, None)."""
    try:
        resp = session.get(url, timeout=20, allow_redirects=True)
    except requests.RequestException:
        return None, None
    if resp.status_code != 200:
        return None, None
    match = LB_TMDB_RE.search(resp.text)
    return (match.group(1), int(match.group(2))) if match else (None, None)


def resolve_target(session, key, meta) -> tuple[str | None, int | None, str]:
    if meta.get("tmdb_id"):
        return meta.get("content_type", "movie"), int(meta["tmdb_id"]), "cached"
    title = meta.get("title")
    movie_id = search_movie(session, key, title, meta.get("year"))
    if movie_id:
        return "movie", movie_id, "search"
    if meta.get("letterboxd"):
        ctype, tid = scrape_letterboxd(session, meta["letterboxd"])
        if tid:
            return ctype, tid, "letterboxd"
    return None, None, "none"


def build_note(meta, data, content_type, cast_size) -> tuple[dict, str]:
    credits = data.get("credits", {})
    cast = [c["name"] for c in credits.get("cast", [])[:cast_size]]
    studios = [s["name"] for s in data.get("production_companies", [])]
    genres = [g["name"] for g in data.get("genres", [])]

    if content_type == "tv":
        director = next((c["name"] for c in data.get("created_by", [])), None)
        release = data.get("first_air_date") or ""
        title = meta.get("title") or data.get("name")
        runtimes = data.get("episode_run_time") or []
        runtime = runtimes[0] if runtimes else None
        keywords = [k["name"] for k in data.get("keywords", {}).get("results", [])]
    else:
        director = next(
            (c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"),
            None,
        )
        release = data.get("release_date") or ""
        title = meta.get("title") or data.get("title")
        runtime = data.get("runtime")
        keywords = [k["name"] for k in data.get("keywords", {}).get("keywords", [])]

    countries = [c["name"] for c in data.get("production_countries", [])]
    country_codes = [c["iso_3166_1"] for c in data.get("production_countries", [])]
    if not country_codes:  # TV (and some films) expose only origin_country codes
        country_codes = data.get("origin_country", [])
        countries = countries or country_codes

    poster = f"{POSTER_BASE}{data['poster_path']}" if data.get("poster_path") else None
    enriched = {
        "type": "film",
        "title": title,
        "year": int(release[:4]) if release[:4].isdigit() else meta.get("year"),
        "tmdb_id": data.get("id") or meta.get("tmdb_id"),
        "content_type": content_type,
        "runtime": runtime,
        "genres": genres,
        "director": director,
        "studios": studios,
        "cast": cast,
        "keywords": keywords,
        "country": countries[0] if countries else None,
        "country_code": country_codes[0].upper() if country_codes else None,
        "language": data.get("original_language"),
        "poster": poster,
        "tags": common.as_list(meta.get("tags")) or ["film"],
    }
    for field in PRESERVE:
        if field in meta:
            enriched[field] = meta[field]
    for key, value in meta.items():  # keep unknown extras (e.g. letterboxd)
        if key not in enriched and key not in FILM_KEY_ORDER:
            enriched[key] = value

    ordered = {k: enriched[k] for k in FILM_KEY_ORDER if enriched.get(k) is not None}
    for key, value in enriched.items():
        if value is not None:  # honor the None-filter above for leftover/extra keys too
            ordered.setdefault(key, value)

    body = render_body(
        director, cast, studios, genres, data.get("overview"),
        watched=meta.get("watched"), rating=meta.get("rating"),
        rewatch=bool(meta.get("rewatch")), log_tags=meta.get("log_tags"),
    )
    return ordered, body


def fmt_date(value) -> str:
    """'2023-02-24' -> '24 Feb 2023'. Built from the string parts (not a real date) so a
    bare ISO date isn't shifted across a timezone; returns the raw string on no match."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(value))
    if not m:
        return str(value)
    year, month, day = m.groups()
    return f"{int(day)} {MONTHS[int(month) - 1]} {year}"


def render_log(watched, rating, rewatch, log_tags) -> str | None:
    """The folded "Log" callout — your Letterboxd diary entry (watched date, rating,
    rewatch flag) and its tags. Returns None when nothing was logged (e.g. Watchlist)."""
    head = []
    if watched:
        head.append("Watched " + fmt_date(watched))
    if rating is not None:
        head.append(f"★ {rating}")
    if rewatch:
        head.append("Rewatch")
    lines = []
    if head:
        lines.append(" · ".join(head))
    tags = common.as_list(log_tags)
    if tags:
        # wikilinks so each tag resolves to its /logs/<tag> hub page (and joins the graph)
        lines.append("Tags  " + " · ".join(common.wikilink(t) for t in tags))
    if not lines:
        return None
    return "> [!note]- Log\n" + "\n".join("> " + ln for ln in lines)


def render_body(director, cast, studios, genres, overview, *,
                watched=None, rating=None, rewatch=False, log_tags=None) -> str:
    """Body = overview prose + a folded "Log" callout (your diary entry) + a folded
    "Cast & crew" callout holding the [[wikilinks]]. The links must live in the note body
    (that's what Quartz's graph and backlinks read), but the film-page component renders
    them prettily from frontmatter — so we tuck them into a folded callout to avoid visible
    duplication while keeping the graph edges. Still fully readable/native in Obsidian."""
    rows = []
    if director:
        rows.append(f"**Director** {common.wikilink(director)}")
    if cast:
        rows.append("**Cast** " + " · ".join(common.wikilink(c) for c in cast))
    if studios:
        rows.append("**Studios** " + " · ".join(common.wikilink(s) for s in studios))
    if genres:
        rows.append("**Genres** " + " · ".join(common.wikilink(g) for g in genres))

    parts = []
    if overview:
        parts.append(overview.strip())
    log = render_log(watched, rating, rewatch, log_tags)
    if log:
        parts.append(log)
    if rows:
        parts.append("> [!info]- Cast & crew\n" + "\n".join("> " + r for r in rows))
    return "\n\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich film notes from TMDB.")
    parser.add_argument("--vault", type=Path, default=Path("vault"))
    parser.add_argument("--folder", default="Films",
                        help="vault subfolder to enrich (default Films; e.g. Watchlist)")
    parser.add_argument("--cast-size", type=int, default=10)
    parser.add_argument("--only", help="only enrich films whose title contains this")
    parser.add_argument("--missing", action="store_true", help="only films with no tmdb_id")
    parser.add_argument("--key", help="TMDB v3 API key (else env/.env)")
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args()

    key = load_key(args.key)
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    enriched = failed = 0

    for path, meta, _body in common.iter_folder_notes(args.vault, args.folder):
        title = meta.get("title") or path.stem
        if args.only and args.only.lower() not in title.lower():
            continue
        if args.missing and meta.get("tmdb_id"):
            continue

        content_type, tmdb_id, method = resolve_target(session, key, meta)
        if not tmdb_id:
            print(f"  ✗ no TMDB match: {title}")
            failed += 1
            continue

        try:
            data = tmdb_get(
                session, f"{content_type}/{tmdb_id}", key,
                append_to_response="credits,keywords",
            )
        except (TMDBError, requests.RequestException) as exc:
            print(f"  ✗ TMDB error for {title}: {exc}")
            failed += 1
            continue

        new_meta, new_body = build_note(meta, data, content_type, args.cast_size)
        common.write_note(path, new_meta, new_body)
        enriched += 1
        tag = f" [{content_type} via {method}]" if method == "letterboxd" else ""
        print(f"  ✓ {new_meta['title']} ({new_meta.get('year')}){tag}")
        time.sleep(args.sleep)

    print(f"\nEnriched={enriched} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
