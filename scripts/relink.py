"""Regenerate film-note bodies from frontmatter — no network.

Rebuilds the [[wikilink]] block using the current `common.link_name` normalization
while preserving any overview prose. Use after a normalization change (so bodies match
the entity filenames), or as a fast relink step in the refresh workflow. Much cheaper
than re-running enrich.py since it makes no TMDB calls.

Usage:
    python scripts/relink.py --vault vault
"""

from __future__ import annotations

import argparse
from pathlib import Path

import common
from enrich import render_body

# Legacy leading link lines ("Director: [[..]]"), superseded by the folded callout.
LINK_PREFIXES = ("Director:", "Cast:", "Studios:", "Genres:")


def extract_overview(body: str) -> str:
    """The overview prose only — drops both the legacy leading link lines and the folded
    "Cast & crew" callout (any `>`-prefixed line), so relinking is idempotent regardless
    of which body format a note currently has."""
    keep = []
    for line in body.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(">"):  # callout block (Cast & crew) — regenerated below
            continue
        if stripped.startswith(LINK_PREFIXES):  # legacy inline link lines
            continue
        keep.append(line)
    return "\n".join(keep).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild film bodies from frontmatter.")
    parser.add_argument("--vault", type=Path, default=Path("vault"))
    parser.add_argument("--folders", nargs="+", default=["Films", "Watchlist"])
    args = parser.parse_args()

    n = 0
    for folder in args.folders:
        for path, meta, body in common.iter_folder_notes(args.vault, folder):
            overview = extract_overview(body)
            new_body = render_body(
                meta.get("director"),
                common.as_list(meta.get("cast")),
                common.as_list(meta.get("studios")),
                common.as_list(meta.get("genres")),
                overview or None,
            )
            common.write_note(path, meta, new_body)
            n += 1

    print(f"Relinked {n} notes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
