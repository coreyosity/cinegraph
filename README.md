# cinegraph

A personal movie platform built from your Letterboxd history + TMDB metadata. One
Markdown note per film in an Obsidian vault, enriched and cross-linked so you can:

- **Analyze** your watching patterns (genres, directors, actors, studios, eras) with
  interactive **Obsidian Bases** queries, and
- **Explore** the relationship graph — and publish it as a personal website with
  **Quartz** (interactive web graph + auto hub pages).
- **Discover** new films via local taste-mining (your own high-rated directors / actors
  / genres), using TMDB only to fetch candidate pools.

See `templates/SCHEMA.md` for the note formats.

## Layout

```
scripts/       pipeline (common utils, enrichment, entity-gen, discovery)
templates/     note schema reference
vault/         the Obsidian vault (= Quartz content root)
  Films/  People/  Studios/  Genres/  Watchlist/  Discover/
  _meta/  _bases/  (Obsidian-only; excluded from the Quartz build)
sample/        synthetic fixtures for testing the scripts
```

## Pipeline (data flow)

```
Letterboxd Pro export ──► Letterboxd Mirror plugin ──► Films/*.md (title/year/rating)
        └─ scripts/enrich.py       fills genres/director/cast/studios/keywords/poster (TMDB)
        └─ scripts/gen_entities.py generates People/Studios/Genres stub notes (graph nodes)
        └─ scripts/discover.py     writes Discover/*.md recommendations
        └─ Quartz build            publishes the vault as a site
```

## Setup (Chunk 0)

1. **Letterboxd Pro** → export your data (Settings → Import & Export → Export). Unzip.
2. **TMDB API key** (free): themoviedb.org → Settings → API → v3 key.
   Create `.env` here with `TMDB_KEY=...` (git-ignored).
3. **Obsidian**: open `vault/` as a vault. Enable the core **Bases** plugin. Install the
   **Letterboxd Mirror** plugin (manual — pending directory approval) and point its
   batch import at your export; target folder `Films/`.
4. **Python**: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
5. **Quartz**: Node 22+ is installed; a clone lives at `../quartz`. Chunk 6 wires it up.

## Usage

**The whole pipeline in one command** (`refresh.sh` chains ingest → enrich → relink →
gen_entities → discover → Quartz build):

```bash
./refresh.sh                      # re-enrich new films, regen entities, re-recommend, rebuild
./refresh.sh ~/path/to/lb-export  # also ingest a fresh Letterboxd export first
```

Or run steps individually:

```bash
python scripts/ingest.py --export ~/path/to/lb-export --vault vault  # export -> bare notes
python scripts/enrich.py --vault vault [--missing]     # TMDB metadata (--missing = new only)
python scripts/relink.py --vault vault                 # rebuild body wikilinks (no network)
python scripts/gen_entities.py --vault vault           # People/Studios/Genres nodes
python scripts/gen_entities.py --vault vault --check    #   verify links only (no writes)
python scripts/discover.py --vault vault               # recommendations -> Discover/
```

Scripts are **idempotent** and never overwrite your Letterboxd `rating`/`watched`
fields or hand-edited stub bodies. A TMDB key is read from `.env` (`TMDB_KEY=...`).

## Development

```bash
make install-dev      # pip install runtime + dev deps into .venv
make check            # ruff (lint) + mypy (types) + pytest — the pre-commit gate
make test             # tests only        make lint / make typecheck — individually
make fmt              # ruff's safe autofixes (imports etc.); does NOT reformat code
```

- **Tests** live in `scripts/tests/` (pure `core/` units + app-layer tests over `tmp_path`
  fixtures). `pytest.ini` and conftest put `scripts/` on the path.
- **Style:** ruff lints but we do **not** run `ruff format` — some code (e.g. the Brandes
  loop in `core/graph.py`) is intentionally compact. Config in `pyproject.toml`.

**Tracked vs generated:** the repo tracks the *inputs* — `vault/Films/` and
`vault/Watchlist/` (your ratings + enriched TMDB metadata) and `vault/_bases/` — but
**git-ignores the generated content** (`People/ Studios/ Genres/ Themes/ Discover/`). After
a fresh clone, rebuild it:

```bash
python scripts/gen_entities.py --vault vault   # entity stubs (local, instant)
python scripts/discover.py --vault vault        # recommendations (needs a TMDB key)
```

The vendored Quartz engine under `site/` is documented in [`site/UPSTREAM.md`](site/UPSTREAM.md).
