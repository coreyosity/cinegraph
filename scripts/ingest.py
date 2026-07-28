"""Chunk 2 (ingest) — Letterboxd export -> bare film notes.

Reads a Letterboxd data export directly (no Pro plugin needed) and writes one bare
film note per watched film into <vault>/Films, plus watchlist entries into
<vault>/Watchlist. `enrich.py` then fills TMDB metadata; `gen_entities.py` builds the
graph nodes.

Sources:
    watched.csv    master list of every film watched  -> Films/
    ratings.csv    rating (0.5-5) by Letterboxd URI    -> merged in
    diary.csv      actual Watched Date + rewatch flag  -> merged in
    watchlist.csv  unseen films                        -> Watchlist/

Idempotent: on re-run, existing notes keep their enriched fields and body; only the
Letterboxd-owned fields (rating / watched / letterboxd / rewatch) are refreshed.

Usage:
    python scripts/ingest.py --export /path/to/letterboxd-export --vault vault
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import common

LB_OWNED = ("rating", "watched", "letterboxd", "rewatch")


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def parse_rating(value: str | None):
    value = (value or "").strip()
    try:
        return float(value)
    except ValueError:
        return None


def build_indexes(export: Path):
    ratings = {
        r["Letterboxd URI"]: parse_rating(r.get("Rating"))
        for r in read_csv(export / "ratings.csv")
    }
    diary: dict[str, dict] = {}
    for row in read_csv(export / "diary.csv"):
        uri = row["Letterboxd URI"]
        # keep the most recent diary entry per film (rows are chronological)
        diary[uri] = {
            "watched": (row.get("Watched Date") or "").strip() or None,
            "rewatch": (row.get("Rewatch") or "").strip().lower() == "yes",
        }
    return ratings, diary


def write_film(vault: Path, subdir: str, used: dict, row: dict, extra: dict) -> None:
    title = row["Name"].strip()
    year = row.get("Year", "").strip()
    year_val = int(year) if year.isdigit() else None

    # Disambiguate duplicate titles (remakes) with the year, then the boxd slug.
    stem = common.link_name(title)
    if stem in used and used[stem] != row["Letterboxd URI"]:
        stem = common.link_name(f"{title} ({year})") if year else stem
    if stem in used and used[stem] != row["Letterboxd URI"]:
        stem = common.link_name(f"{title} {row['Letterboxd URI'].rsplit('/', 1)[-1]}")
    used[stem] = row["Letterboxd URI"]

    path = vault / subdir / f"{stem}.md"
    meta = {"type": "film", "title": title, "year": year_val}
    meta.update({k: v for k, v in extra.items() if v is not None})
    meta["letterboxd"] = row["Letterboxd URI"]
    meta["tags"] = [subdir.lower().rstrip("s")] if subdir == "Watchlist" else ["film"]

    if path.exists():  # preserve enrichment; refresh only Letterboxd-owned fields
        existing, body = common.read_note(path)
        for field in LB_OWNED:
            if field in meta:
                existing[field] = meta[field]
        common.write_note(path, existing, body)
    else:
        common.write_note(path, meta, "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a Letterboxd export.")
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--vault", type=Path, default=Path("vault"))
    args = parser.parse_args()

    ratings, diary = build_indexes(args.export)

    used: dict[str, str] = {}
    n_films = 0
    for row in read_csv(args.export / "watched.csv"):
        uri = row["Letterboxd URI"]
        extra = {
            "rating": ratings.get(uri),
            "watched": (diary.get(uri, {}).get("watched")) or row.get("Date"),
            "rewatch": diary.get(uri, {}).get("rewatch") or None,
        }
        write_film(args.vault, "Films", used, row, extra)
        n_films += 1

    used_wl: dict[str, str] = {}
    n_wl = 0
    for row in read_csv(args.export / "watchlist.csv"):
        write_film(args.vault, "Watchlist", used_wl, row, {})
        n_wl += 1

    print(f"Films: {n_films}  |  Watchlist: {n_wl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
