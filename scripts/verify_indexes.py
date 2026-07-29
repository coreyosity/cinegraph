"""Verify a built site actually carries its data indexes — the deploy's last gate.

The client is a static site reading baked JSON, so a build that drops these files still
"succeeds": every page renders, and the interactive views just show "Could not load
films.json". Nothing in the build fails, so this ran green all the way to production.
That's the failure this guards, by checking the shipped output rather than the code.

Also asserts the invariant `split_detail` relies on: films.json and films-detail.json are
index-aligned, so the client merges detail row i into film i only when the lengths agree.
If they drift, keywords/related/taste-map data silently never merge onto any film.

Empty discover/watchlist payloads are a warning, not a failure: a deploy without a TMDB
key legitimately skips the discover step (see .github/workflows/deploy.yml).

Usage:
    python scripts/verify_indexes.py --site site
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# index name -> the key holding its list of records
PAYLOADS = {
    "films.json": "films",
    "films-detail.json": "detail",
    "discover.json": "recs",
    "watchlist.json": "watchlist",
}

# Indexes that must be non-empty for the site to be worth shipping. discover/watchlist can
# legitimately be empty (no TMDB key, empty watchlist), so they only warn.
REQUIRED_NON_EMPTY = ("films.json", "films-detail.json")


def verify(static_dir: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for the data indexes in `static_dir`."""
    errors: list[str] = []
    warnings: list[str] = []
    records: dict[str, int] = {}

    for name, key in PAYLOADS.items():
        path = static_dir / name
        if not path.exists():
            errors.append(f"{name} is missing from {static_dir}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{name} is not valid JSON ({exc})")
            continue
        if key not in payload:
            errors.append(f"{name} has no '{key}' key")
            continue

        rows = payload[key]
        records[name] = len(rows)
        if payload.get("count") != len(rows):
            errors.append(f"{name}: count={payload.get('count')} but {len(rows)} {key} rows")
        if not rows:
            target = errors if name in REQUIRED_NON_EMPTY else warnings
            target.append(f"{name} is empty")

    # The index-alignment contract between the two film payloads (see gen_index.split_detail).
    if (
        "films.json" in records
        and "films-detail.json" in records
        and records["films.json"] != records["films-detail.json"]
    ):
        errors.append(
            f"films.json ({records['films.json']} rows) and films-detail.json "
            f"({records['films-detail.json']} rows) are not index-aligned; "
            "the client will refuse to merge detail onto any film"
        )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the built site's data indexes.")
    parser.add_argument("--site", type=Path, default=Path("site"))
    args = parser.parse_args()

    static_dir = args.site / "public" / "static"
    errors, warnings = verify(static_dir)

    for warning in warnings:
        print(f"  ⚠ {warning}")
    if errors:
        for error in errors:
            print(f"  ✗ {error}")
        print(f"✗ data indexes failed verification ({len(errors)} problem(s))")
        return 1
    print(f"✓ data indexes verified in {static_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
