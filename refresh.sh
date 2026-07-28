#!/usr/bin/env bash
# cinegraph refresh — run the whole pipeline end to end.
#
#   ./refresh.sh                      # re-enrich new films, regen entities, re-recommend, rebuild site
#   ./refresh.sh /path/to/lb-export   # also ingest a fresh Letterboxd export first
#
# Needs a TMDB key: put TMDB_KEY=... in ./.env (the python scripts read it on their own).

cd "$(dirname "$0")"
PY=.venv/bin/python
EXPORT="${1:-}"

set -e

if [ -n "$EXPORT" ]; then
  echo "▶ 1/7  ingest  ($EXPORT)"
  $PY scripts/ingest.py --export "$EXPORT" --vault vault
else
  echo "▶ 1/7  ingest  — skipped (no export path given)"
fi

echo "▶ 2/7  enrich new films + watchlist"
$PY scripts/enrich.py --vault vault --missing || true   # non-zero is benign (unmatchable TV episodes)
$PY scripts/enrich.py --vault vault --folder Watchlist --missing || true  # posters + graph links for watchlist

echo "▶ 3/7  relink film bodies"
$PY scripts/relink.py --vault vault

echo "▶ 4/7  regenerate entity notes"
$PY scripts/gen_entities.py --vault vault

echo "▶ 5/7  discover recommendations"
$PY scripts/discover.py --vault vault
$PY scripts/gen_providers.py --vault vault || true   # streaming availability for watchlist/discover
# ('Up Next' folds in the old gen_missed logic — predicted watchlist ranking lives in gen_index)

if [ ! -d site ]; then
  echo "▶ 6/7  build site — skipped (no site/ dir)"
elif pgrep -f "quartz build --serve" >/dev/null; then
  echo "▶ 6/7  build — skipped (quartz --serve is live and hot-reloads automatically)"
else
  echo "▶ 6/7  build Quartz site"
  ( cd site && rm -rf public && npx quartz build )   # clean slate avoids ENOTEMPTY
fi

# Runs last: it reads the build's static/contentIndex.json for canonical page slugs.
# With --serve live (build skipped above) it reads serve's live index instead — fine.
echo "▶ 7/7  data index (films.json for client-side views)"
$PY scripts/gen_index.py --vault vault --site site

echo "✓ cinegraph refresh complete"
