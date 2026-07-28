"""Add streaming availability ("where to watch") to notes.

Uses TMDB's free `/{type}/{id}/watch/providers` endpoint (JustWatch data, no extra
account). A single call returns every region, so we merge the **flatrate** (subscription)
services across a set of regions — handy with a VPN, where you're not tied to one country.
Results are written to each note's `providers` frontmatter list.

Covers watched films *and* the to-watch folders by default, so film pages can show where
to stream. Idempotent: rewrites `providers` each run, clears it when nothing streams.

Usage:
    python scripts/gen_providers.py --vault vault
    python scripts/gen_providers.py --vault vault --regions IE US GB
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import requests

import common
from enrich import TMDBError, load_key, tmdb_get  # reuse the enrich TMDB plumbing

# Regions to merge, in priority order (a VPN makes all of these reachable).
DEFAULT_REGIONS = ["IE", "GB", "US", "CA", "AU"]


def providers_for(session, key, ctype: str, tmdb_id: int, regions: list[str]) -> list[str]:
    """Union of flatrate service names across `regions`, de-duplicated, priority order."""
    results = tmdb_get(session, f"{ctype}/{tmdb_id}/watch/providers", key).get("results", {})
    seen, out = set(), []
    for region in regions:
        for prov in results.get(region, {}).get("flatrate", []) or []:
            name = prov["provider_name"]
            if name not in seen:
                seen.add(name)
                out.append(name)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Add streaming providers to notes.")
    parser.add_argument("--vault", type=Path, default=Path("vault"))
    parser.add_argument("--folders", nargs="+", default=["Films", "Watchlist", "Discover"])
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS,
                        help="ISO regions to merge (default: IE GB US CA AU)")
    parser.add_argument("--key")
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args()

    key = load_key(args.key)
    session = requests.Session()
    updated = failed = with_stream = 0

    for folder in args.folders:
        for path, meta, body in common.iter_folder_notes(args.vault, folder):
            tmdb_id = meta.get("tmdb_id")
            if not tmdb_id:
                continue
            ctype = meta.get("content_type", "movie")
            try:
                names = providers_for(session, key, ctype, int(tmdb_id), args.regions)
            except (TMDBError, requests.RequestException) as exc:
                print(f"  ✗ {meta.get('title') or path.stem}: {exc}")
                failed += 1
                continue
            if names:
                meta["providers"] = names
                with_stream += 1
            else:
                meta.pop("providers", None)
            common.write_note(path, meta, body)
            updated += 1
            time.sleep(args.sleep)

    print(f"\nChecked={updated} streamable={with_stream} failed={failed} "
          f"regions={'/'.join(args.regions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
