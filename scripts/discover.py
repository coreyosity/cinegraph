"""Chunk 5 — Discovery engine (local taste-mining).

Recommends unseen films personalized to YOUR ratings, using TMDB only to fetch a
candidate pool (not as the ranker — that avoids TMDB's popularity bias):

1. Build a rating-weighted taste profile from rated films: each film adds
   (rating - baseline) to the weight of its director / actors / genres / keywords.
2. Seeds = your highest-rated films. For each, pull TMDB /recommendations + /similar,
   tracking which seeds surfaced each candidate.
3. Score a candidate by how strongly your loved films point to it (seed affinity) PLUS
   its overlap with your taste profile. Dedup vs watched / watchlist / dismissed.
4. Write ranked Discover/*.md, each with a "Why" that links back to the triggering films.

Re-runnable: Discover/*.md is rewritten each run; Discover/_dismissed/ is preserved and
its films never resurface (move a rec there, or set `dismissed: true`, to dismiss it).

Usage:
    python scripts/discover.py --vault vault
    python scripts/discover.py --vault vault --count 40 --max-seeds 80
"""

from __future__ import annotations

import argparse
from pathlib import Path

import requests

import common
from core.recommend import score_candidate, seed_affinity
from core.taste import build_profile  # one shared taste model (also powers Up Next)
from enrich import POSTER_BASE, UA, TMDBError, load_key, tmdb_get


def read_films(vault: Path):
    return common.load_films(vault)  # core.Film objects for the taste profile


def norm_key(title: str, year) -> tuple[str, str]:
    return (common.link_name(title or "").lower(), str(year or ""))


def collect_exclusions(vault: Path):
    """watched tmdb_ids, watchlist (title,year) keys, and dismissed tmdb_ids."""
    watched_ids, watchlist_keys, dismissed_ids = set(), set(), set()
    for _p, meta, _b in common.iter_film_notes(vault):
        if meta.get("tmdb_id"):
            watched_ids.add(int(meta["tmdb_id"]))
    for path in (vault / "Watchlist").glob("*.md"):
        meta, _b = common.read_note(path)
        watchlist_keys.add(norm_key(meta.get("title", path.stem), meta.get("year")))
    dismissed_dir = vault / "Discover" / "_dismissed"
    for path in dismissed_dir.glob("*.md") if dismissed_dir.exists() else []:
        meta, _b = common.read_note(path)
        if meta.get("tmdb_id"):
            dismissed_ids.add(int(meta["tmdb_id"]))
    for path in (vault / "Discover").glob("*.md"):
        meta, _b = common.read_note(path)
        if meta.get("dismissed") and meta.get("tmdb_id"):
            dismissed_ids.add(int(meta["tmdb_id"]))
    return watched_ids, watchlist_keys, dismissed_ids


def pick_seeds(films, vault, seed_min, max_seeds):
    seeds = []
    for _p, meta, _b in common.iter_film_notes(vault):
        rating = meta.get("rating")
        if (
            isinstance(rating, (int, float))
            and rating >= seed_min
            and meta.get("tmdb_id")
            and meta.get("content_type", "movie") != "tv"
        ):
            seeds.append((int(meta["tmdb_id"]), _p.stem, rating, meta.get("title")))
    seeds.sort(key=lambda s: s[2], reverse=True)
    return seeds[:max_seeds]


def gather_candidates(session, key, seeds, watched_ids, watchlist_keys, dismissed_ids):
    cands: dict[int, dict] = {}
    for sid, stem, rating, _title in seeds:
        for kind in ("recommendations", "similar"):
            try:
                results = tmdb_get(session, f"movie/{sid}/{kind}", key).get("results", [])
            except (TMDBError, requests.RequestException):
                continue
            for r in results:
                cid = r.get("id")
                year = (r.get("release_date") or "")[:4]
                if (
                    not cid
                    or cid in watched_ids
                    or cid in dismissed_ids
                    or norm_key(r.get("title", ""), year) in watchlist_keys
                ):
                    continue
                c = cands.setdefault(
                    cid,
                    {
                        "id": cid,
                        "title": r.get("title"),
                        "year": int(year) if year.isdigit() else None,
                        "genre_ids": set(r.get("genre_ids") or []),
                        "vote": r.get("vote_average") or 0,
                        "votes": r.get("vote_count") or 0,
                        "poster": r.get("poster_path"),
                        "overview": r.get("overview"),
                        "seeds": [],
                    },
                )
                c["seeds"].append((stem, rating))
    return cands


def refine_and_write(session, key, pool, profile, baseline, vault, count, people_pages, theme_pages):
    scored, gated = [], 0
    for cand in pool:
        try:
            data = tmdb_get(
                session, f"movie/{cand['id']}", key,
                append_to_response="credits,keywords",
            )
        except (TMDBError, requests.RequestException):
            continue
        credits = data.get("credits", {})
        director = next(
            (c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"),
            None,
        )
        cast = [c["name"] for c in credits.get("cast", [])[:10]]
        genres = [g["name"] for g in data.get("genres", [])]
        keywords = [k["name"] for k in data.get("keywords", {}).get("keywords", [])]

        result = score_candidate(profile, director, cast, genres, keywords,
                                 seed_affinity(cand["seeds"], baseline), cand["vote"])
        if result is None:  # gate — require a real taste match, not just TMDB's graph
            gated += 1
            continue
        scored.append({
            **cand, **result, "director": director, "genres": genres,
            "cast": cast, "keywords": keywords,
            "overview": data.get("overview"), "poster_path": data.get("poster_path"),
        })

    scored.sort(key=lambda c: c["score"], reverse=True)
    for cand in scored[:count]:
        write_recommendation(vault, cand, people_pages, theme_pages)
    print(f"(gated out {gated} candidates with no specific taste match)")
    return scored[:count]


def _link_existing(name: str, pages: set) -> str:
    """[[wikilink]] if a page for `name` exists, else plain text (never a broken link)."""
    return f"[[{common.link_name(name)}]]" if common.link_name(name) in pages else name


def build_why(cand: dict, theme_pages: set) -> str:
    top_seeds = sorted(cand["seeds"], key=lambda s: s[1], reverse=True)[:3]
    parts = [
        "surfaced by films you rated highly: "
        + ", ".join(f"[[{stem}]] ({r:g}★)" for stem, r in top_seeds)
    ]
    if cand.get("why_director"):
        parts.append(f"more from [[{common.link_name(cand['why_director'])}]], whom you rate highly")
    if cand.get("why_actor"):
        parts.append(f"features [[{common.link_name(cand['why_actor'])}]], an actor you favor")
    if cand.get("why_keywords"):
        parts.append("themes you like: " + ", ".join(_link_existing(k, theme_pages) for k in cand["why_keywords"]))
    if cand.get("why_genres"):
        parts.append("genres you favor: " + ", ".join(f"[[{common.link_name(g)}]]" for g in cand["why_genres"]))
    return "; ".join(parts)


def write_recommendation(vault: Path, cand: dict, people_pages: set, theme_pages: set) -> None:
    stem = common.link_name(f"{cand['title']} ({cand['year']})" if cand.get("year") else cand["title"])
    # Only link cast/themes that already have pages in the vault (i.e. entities you've
    # met elsewhere), so every chip on the recommendation page resolves.
    cast = [c for c in cand.get("cast", []) if common.link_name(c) in people_pages][:8]
    themes = [k for k in cand.get("keywords", []) if common.link_name(k) in theme_pages][:12]
    meta = {
        "type": "recommendation",
        "title": cand["title"],
        "year": cand.get("year"),
        "tmdb_id": cand["id"],
        "score": round(cand["score"], 2),
        "tmdb_rating": round(cand["vote"], 1),
        "director": cand.get("director"),
        "genres": cand.get("genres") or None,
        "cast": cast or None,
        "themes": themes or None,
        "poster": f"{POSTER_BASE}{cand['poster_path']}" if cand.get("poster_path") else None,
        "tags": ["recommendation"],
    }
    meta = {k: v for k, v in meta.items() if v is not None}
    body = f"**Why:** {build_why(cand, theme_pages)}"
    if cand.get("overview"):
        body += f"\n\n{cand['overview']}"
    common.write_note(vault / "Discover" / f"{stem}.md", meta, body)


def clear_old(vault: Path) -> None:
    for path in (vault / "Discover").glob("*.md"):
        path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate film recommendations.")
    parser.add_argument("--vault", type=Path, default=Path("vault"))
    parser.add_argument("--baseline", type=float, default=None,
                        help="rating that counts as neutral (default: your mean rating)")
    parser.add_argument("--seed-min", type=float, default=4.0)
    parser.add_argument("--max-seeds", type=int, default=80)
    parser.add_argument("--pool", type=int, default=120, help="candidates to fetch details for")
    parser.add_argument("--count", type=int, default=40, help="recommendations to write")
    parser.add_argument("--min-votes", type=int, default=100,
                        help="drop candidates with fewer TMDB votes (obscure noise)")
    parser.add_argument("--key")
    args = parser.parse_args()

    key = load_key(args.key)
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    films = read_films(args.vault)
    rated = [f.rating for f in films if f.rating is not None]
    baseline = args.baseline if args.baseline is not None else round(sum(rated) / len(rated), 2)
    profile = build_profile(films, baseline)
    watched_ids, watchlist_keys, dismissed_ids = collect_exclusions(args.vault)
    seeds = pick_seeds(films, args.vault, args.seed_min, args.max_seeds)
    print(f"Taste profile from {len(rated)} rated films (baseline {baseline}).")
    print(f"Seeds: {len(seeds)} | fetching candidate pools...")

    cands = gather_candidates(session, key, seeds, watched_ids, watchlist_keys, dismissed_ids)
    popular = [c for c in cands.values() if c.get("votes", 0) >= args.min_votes]
    pool = sorted(popular, key=lambda c: seed_affinity(c["seeds"], baseline), reverse=True)[: args.pool]
    print(f"Candidates: {len(cands)} unseen ({len(popular)} with >={args.min_votes} votes)"
          f" | refining top {len(pool)}...")

    # Existing entity pages — so recommendation chips only link to entities you have.
    people_pages = {p.stem for p in (args.vault / "People").glob("*.md")}
    theme_pages = {p.stem for p in (args.vault / "Themes").glob("*.md")}

    clear_old(args.vault)
    written = refine_and_write(session, key, pool, profile, baseline, args.vault, args.count,
                               people_pages, theme_pages)
    print(f"\nWrote {len(written)} recommendations to Discover/. Top 10:")
    for c in written[:10]:
        print(f"  {c['score']:6.1f}  {c['title']} ({c.get('year')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
