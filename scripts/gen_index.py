"""Emit the films.json data indexes for the site's client-side views.

The film records are split across two files: `films.json` (the core fields every view
needs) and `films-detail.json` (the heavy tail — keywords, similarity edges, taste-map
markers — that only Stats, film pages, and the constellation read). Most pages on the
site are entity pages that need the core alone, so the tail is fetched on demand rather
than bundled into every page load. See `split_detail`.


Quartz is a *static* build, so interactive views (poster grid, stats dashboard,
sortable/filterable tables) can't query the vault at runtime. Instead we bake one
compact JSON index of every film at build time and let client JS read it.

The film *metadata* (rating, genres, director, poster, ...) lives in each note's
frontmatter. The canonical *URL slug* for each film page is owned by Quartz, so we
read it from the build's `static/contentIndex.json` (joined on the note's path)
rather than re-deriving Quartz's slugify — which would drift and break links. Films
not yet in the index (e.g. added since the last build) fall back to a computed slug.

Output is written to `<site>/public/static/films.json` — the built site's output, which is
what the browser fetches. If the site hasn't been built yet (`public/` absent) it falls back
to `<site>/quartz/static/`. We deliberately do NOT write into `quartz/static` when `public/`
exists: a live `quartz build --serve` *watches* that dir, so a write there kicks off a full
rebuild that both drops the server for minutes and wipes these files from `public/static`
(the build copies static assets but excludes `.json`) → the browser's "Could not load
films.json". `public/` is build output (unwatched), so writing there serves immediately.

Usage:
    python scripts/gen_index.py --vault vault --site site
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from common import (
    as_list,
    canonical,
    iter_film_notes,
    iter_folder_notes,
    link_name,
    load_films,
)
from core import taste
from core.film import Film
from core.graph import attach_related, attach_taste_map

_WIKILINK = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\]")


def load_slug_map(content_index: Path) -> dict[str, str]:
    """Map each note's source path ("Films/Foo.md") to its canonical Quartz slug."""
    if not content_index.exists():
        return {}
    data = json.loads(content_index.read_text(encoding="utf-8"))
    return {entry["filePath"]: entry["slug"] for entry in data.values() if entry.get("filePath")}


def fallback_slug(title: str) -> str:
    """Approximate Quartz's slug for a film missing from the (stale) content index."""
    return "films/" + re.sub(r"\s+", "-", str(title).strip().lower())


def build_records(vault: Path, slugs: dict[str, str]) -> list[dict]:
    films: list[dict] = []
    for path, meta, _body in iter_film_notes(vault):
        rel = path.relative_to(vault).as_posix()
        slug = slugs.get(rel) or fallback_slug(path.stem)
        films.append(
            {
                "title": meta.get("title") or path.stem,
                "year": meta.get("year"),
                "rating": meta.get("rating"),
                "runtime": meta.get("runtime"),
                "director": meta.get("director"),
                "cast": as_list(meta.get("cast")),
                "genres": as_list(meta.get("genres")),
                "studios": as_list(meta.get("studios")),
                "keywords": as_list(meta.get("keywords")),
                "country": meta.get("country"),
                "country_code": meta.get("country_code"),
                "language": meta.get("language"),
                "poster": meta.get("poster"),
                "tmdb_id": meta.get("tmdb_id"),
                "url": "/" + slug,
            }
        )
    # Default order: highest-rated first, newest as tiebreak; unrated/undated sink.
    films.sort(key=lambda f: (f["rating"] or -1, f["year"] or -1), reverse=True)
    attach_related(films)
    attach_themes(films, vault)
    return films


def attach_themes(films: list[dict], vault: Path) -> None:
    """Add `themes` per film: the subset of its keywords that have a Theme page (i.e.
    keywords frequent enough that gen_entities emitted a stub). Used for clickable theme
    chips on film pages that always resolve."""
    themed = {p.stem for p in (vault / "Themes").glob("*.md")}
    for f in films:
        seen, out = set(), []
        for kw in f.get("keywords") or []:
            ln = link_name(kw)
            if ln in themed and ln not in seen:
                seen.add(ln)
                out.append(canonical(kw))
        f["themes"] = out


# Fields only the Stats dashboard, film pages, and the constellation read. Every other
# view (poster grids, People/Studio/Genre pages, Ensemble) needs none of them, so they
# ship separately and are fetched on demand — see `split_detail`.
DETAIL_FIELDS = ("keywords", "related", "community", "bridge", "orphan")


def split_detail(films: list[dict]) -> tuple[list[dict], list[dict]]:
    """Partition each film record into a core payload and the heavy tail above.

    The two lists are *index-aligned* rather than joined on tmdb_id: they're written from
    one list in one run, so position is a stable key, and it costs no repeated id per row
    (and still works for the films with no tmdb_id). The client merges row i into film i
    only when the lengths agree, so a stale cached films.json can't mis-join.
    """
    core = [{k: v for k, v in f.items() if k not in DETAIL_FIELDS} for f in films]
    detail = [{k: f[k] for k in DETAIL_FIELDS if k in f} for f in films]
    return core, detail


def build_discover_records(vault: Path, slugs: dict[str, str]) -> list[dict]:
    """Discover recommendations for the client-side gallery: metadata + the human 'why'
    (its wikilinks flattened to plain titles for card display). Dismissed recs (in
    Discover/_dismissed/) are naturally excluded — iter_folder_notes only reads the top level."""
    recs: list[dict] = []
    for path, meta, body in iter_folder_notes(vault, "Discover"):
        if meta.get("type") != "recommendation":
            continue
        rel = path.relative_to(vault).as_posix()
        slug = slugs.get(rel) or fallback_slug(path.stem).replace("films/", "discover/")
        why = ""
        for line in body.splitlines():
            if line.strip().startswith("**Why:**"):
                why = _WIKILINK.sub(r"\1", line.split("**Why:**", 1)[1]).strip()
                break
        recs.append({
            "title": meta.get("title") or path.stem,
            "year": meta.get("year"),
            "score": meta.get("score"),
            "tmdb_rating": meta.get("tmdb_rating"),
            "director": meta.get("director"),
            "genres": as_list(meta.get("genres")),
            "providers": as_list(meta.get("providers")),
            "poster": meta.get("poster"),
            "tmdb_id": meta.get("tmdb_id"),
            "why": why,
            "url": "/" + slug,
        })
    recs.sort(key=lambda r: (r["score"] or -1), reverse=True)
    return recs


def build_watchlist_records(vault: Path, slugs: dict[str, str], profile, baseline) -> list[dict]:
    """Watchlist films scored by the shared taste model — a predicted rating + a reason
    from the strongest drivers. Directors/themes you rate highly rise to the top (this
    absorbs the old 'Missed' page)."""
    recs: list[dict] = []
    for path, meta, _body in iter_folder_notes(vault, "Watchlist"):
        predicted, drivers = taste.predict(profile, baseline, Film.from_note(meta))
        rel = path.relative_to(vault).as_posix()
        slug = slugs.get(rel) or fallback_slug(path.stem).replace("films/", "watchlist/")
        recs.append({
            "title": meta.get("title") or path.stem,
            "year": meta.get("year"),
            "runtime": meta.get("runtime"),
            "director": meta.get("director"),
            "genres": as_list(meta.get("genres")),
            "providers": as_list(meta.get("providers")),
            "poster": meta.get("poster"),
            "tmdb_id": meta.get("tmdb_id"),
            "predicted": predicted,
            "reason": taste.describe(drivers),
            "url": "/" + slug,
        })
    recs.sort(key=lambda r: (r["predicted"] or -1, r["year"] or -1), reverse=True)
    return recs


def write_json(site: Path, name: str, payload: dict) -> list[Path]:
    """Write a data index to the site. Prefer the built output dir (`public/static`) and,
    when it exists, write ONLY there — never `quartz/static`, which a live `--serve` watches
    (a write there triggers a clobbering rebuild; see the module docstring). Falls back to
    `quartz/static` only when the site hasn't been built yet."""
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    public_static = site / "public" / "static"
    if public_static.exists():
        targets = [public_static / name]
    else:
        targets = [site / "quartz" / "static" / name]
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(blob, encoding="utf-8")
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit films.json for client-side views.")
    parser.add_argument("--vault", type=Path, default=Path("vault"))
    parser.add_argument("--site", type=Path, default=Path("site"))
    args = parser.parse_args()

    slugs = load_slug_map(args.site / "public" / "static" / "contentIndex.json")
    now = datetime.now(UTC).isoformat(timespec="seconds")
    films = build_records(args.vault, slugs)
    islands = attach_taste_map(films)
    core, detail = split_detail(films)
    targets = write_json(args.site, "films.json",
                         {"generated": now, "count": len(core), "films": core})
    write_json(args.site, "films-detail.json",
               {"generated": now, "count": len(detail), "islands": islands, "detail": detail})

    recs = build_discover_records(args.vault, slugs)
    write_json(args.site, "discover.json", {"generated": now, "count": len(recs), "recs": recs})

    rated = [f for f in load_films(args.vault) if f.rating is not None]
    baseline = taste.baseline_of(rated)
    profile = taste.build_profile(rated, baseline)
    acc = taste.backtest(rated)
    watch = build_watchlist_records(args.vault, slugs, profile, baseline)
    write_json(args.site, "watchlist.json", {
        "generated": now, "count": len(watch),
        "accuracy": {"mae": round(acc["mae"], 2), "r": round(acc["r"], 2), "n": acc["n"]},
        "watchlist": watch,
    })

    missing = sum(1 for path, _m, _b in iter_film_notes(args.vault)
                  if path.relative_to(args.vault).as_posix() not in slugs)
    print(f"✓ films.json — {len(core)} films (+ films-detail.json), "
          f"discover.json — {len(recs)} recs → {', '.join(str(t) for t in targets)}")
    if missing:
        print(f"  ⚠ {missing} film(s) not in content index yet; used fallback slugs "
              f"(rebuild the site to refresh their URLs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
