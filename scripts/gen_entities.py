"""Chunk 3 — Entity-note generation.

Scans every film note's frontmatter, collects the unique set of directors, actors,
studios, and genres, and generates a stub note per entity so they become real nodes
(and auto hub pages via backlinks) in the Obsidian *and* Quartz graphs. Without real
files, Quartz renders these links as broken "Untitled" 404s.

Each stub carries a generated `film_count` (how many of your films reference it), which
powers the Bases analysis views and the eventual actor-threshold decision.

Idempotent: existing stubs are never body-overwritten; a person's `roles` are merged and
`film_count` refreshed. People live in a flat `People/` folder (a director who also acts
is one note with roles [actor, director]) to avoid duplicate basenames, which would make
`[[Name]]` ambiguous.

Usage:
    python scripts/gen_entities.py --vault vault
    python scripts/gen_entities.py --vault vault --check   # verify only, write nothing
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import common

# Folders whose film notes carry body [[wikilinks]] that must resolve to stubs. Only
# Films are *watched*, so film_count / avg_rating are computed from Films alone; the
# Watchlist is scanned purely so its entity links resolve (no "Untitled" graph nodes).
WATCHED_FOLDER = "Films"
LINKED_FOLDERS = ("Films", "Watchlist")


def collect_entities(vault: Path):
    people_roles: dict[str, set[str]] = defaultdict(set)  # name -> {roles}
    counts: dict[str, Counter[str]] = {"person": Counter(), "studio": Counter(),
                                       "genre": Counter(), "theme": Counter(),
                                       "tag": Counter()}
    # name -> list of your ratings on the (rated) films linking this entity. Powers the
    # taste-ranked Bases views ("your best directors/actors/genres/studios").
    ratings: dict[str, defaultdict[str, list[float]]] = {
        "person": defaultdict(list), "studio": defaultdict(list),
        "genre": defaultdict(list), "theme": defaultdict(list),
        "tag": defaultdict(list)}
    # Entities seen only on the (unwatched) Watchlist still need a stub so their links
    # resolve; tracked here so they get created with film_count 0.
    seen_simple: dict[str, set[str]] = {"studio": set(), "genre": set()}

    for folder in LINKED_FOLDERS:
        watched = folder == WATCHED_FOLDER
        for _path, meta, _body in common.iter_folder_notes(vault, folder):
            rating = meta.get("rating")
            rating = float(rating) if watched and isinstance(rating, (int, float)) else None
            people_in_film: set[str] = set()
            director = meta.get("director")
            if director:
                name = common.canonical(director)
                people_roles[name].add("director")
                people_in_film.add(name)
            for actor in common.as_list(meta.get("cast")):
                name = common.canonical(actor)
                people_roles[name].add("actor")
                people_in_film.add(name)
            studios = {common.canonical(s) for s in common.as_list(meta.get("studios"))}
            genres = {common.canonical(g) for g in common.as_list(meta.get("genres"))}
            themes = set(common.theme_keywords(meta.get("keywords")))
            seen_simple["studio"] |= studios
            seen_simple["genre"] |= genres
            if not watched:
                continue
            for name in people_in_film:  # count each film once per person
                counts["person"][name] += 1
                if rating is not None:
                    ratings["person"][name].append(rating)
            log_tags = set(common.as_list(meta.get("log_tags")))
            for field, values in (("studio", studios), ("genre", genres),
                                  ("theme", themes), ("tag", log_tags)):
                for value in values:
                    counts[field][value] += 1
                    if rating is not None:
                        ratings[field][value].append(rating)

    # Register Watchlist-only studios/genres (people are already in people_roles) with a
    # zero watched-count so the main loop still emits their stubs.
    for etype in ("studio", "genre"):
        for name in seen_simple[etype]:
            if name not in counts[etype]:
                counts[etype][name] = 0

    return people_roles, counts, ratings


def _rating_stats(values: list[float]) -> tuple[float | None, int]:
    """(mean rounded to 2dp, count) over an entity's rated films; (None, 0) if none."""
    return (round(sum(values) / len(values), 2), len(values)) if values else (None, 0)


def _apply_visibility(meta: dict, hide: bool) -> None:
    """Hide (or unhide) an entity in *both* graphs, keeping its page + backlinks.

    - **Quartz** honours `unlisted: true` (content-index drops the page → the node
      leaves the web graph, search, and RSS). Quartz's graph `removeTags` only filters
      *tag* nodes, never content nodes, so a tag alone can't hide these on the web.
    - **Obsidian**'s graph filters on `-tag:#graph-hide` (see `.obsidian/graph.json`),
      so we keep that tag for the local workbench graph.

    Whether an entity is hidden is decided by the caller from `cinegraph.yaml`
    thresholds (see `main`), so this just writes the two markers consistently.
    """
    tags = [t for t in meta.get("tags", []) if t != "graph-hide"]
    if hide:
        meta["unlisted"] = True
        tags.append("graph-hide")
    else:
        meta.pop("unlisted", None)
    meta["tags"] = tags


def _apply_rating(meta: dict, avg_rating: float | None, rated_count: int) -> None:
    """Write (or clear) an entity's taste stats — the mean of your ratings on its films.
    Cleared when none of its films are rated, so the field stays truthful as you rate."""
    if rated_count:
        meta["avg_rating"] = avg_rating
        meta["rated_count"] = rated_count
    else:
        meta.pop("avg_rating", None)
        meta.pop("rated_count", None)


def ensure_person(
    vault: Path, name: str, roles: set[str], film_count: int, hide: bool,
    avg_rating: float | None, rated_count: int,
) -> str:
    path = vault / "People" / f"{common.link_name(name)}.md"
    if path.exists():
        meta, body = common.read_note(path)
        merged = sorted(set(common.as_list(meta.get("roles"))) | roles)
        meta["type"] = "person"
        meta["roles"] = merged
        meta["film_count"] = film_count
        meta["tags"] = ["person", *merged]
        _apply_visibility(meta, hide)
        _apply_rating(meta, avg_rating, rated_count)
        common.write_note(path, meta, body)
        return "updated"
    meta = {
        "type": "person",
        "roles": sorted(roles),
        "film_count": film_count,
        "tags": ["person", *sorted(roles)],
    }
    _apply_visibility(meta, hide)
    _apply_rating(meta, avg_rating, rated_count)
    common.write_note(path, meta, f"# {common.canonical(name)}")
    return "created"


def ensure_simple(
    vault: Path, subdir: str, name: str, etype: str, film_count: int, hide: bool,
    avg_rating: float | None, rated_count: int,
) -> str:
    path = vault / subdir / f"{common.link_name(name)}.md"
    if path.exists():
        meta, body = common.read_note(path)
        meta["type"] = etype
        meta["film_count"] = film_count
        meta["tags"] = [etype]
        _apply_visibility(meta, hide)
        _apply_rating(meta, avg_rating, rated_count)
        common.write_note(path, meta, body)
        return "updated"
    meta = {"type": etype, "film_count": film_count, "tags": [etype]}
    _apply_visibility(meta, hide)
    _apply_rating(meta, avg_rating, rated_count)
    common.write_note(path, meta, f"# {common.canonical(name)}")
    return "created"


def ensure_tag(
    vault: Path, tag: str, film_count: int, avg_rating: float | None, rated_count: int,
) -> str:
    """A /logs/<tag> hub page for a Letterboxd diary tag. Unlike studios/genres, the display
    name is written explicitly (`title`) — it's the exact key the site's client matches
    against each film's raw `log_tags`, robust to tags like 'disney+' or 'tv show'. Always
    listed (no graph-hide): the film→tag wikilinks make these first-class graph nodes."""
    path = vault / "Logs" / f"{common.link_name(tag)}.md"
    if path.exists():
        meta, body = common.read_note(path)
        meta["type"] = "logtag"
        meta["title"] = tag
        meta["film_count"] = film_count
        meta["tags"] = ["logtag"]
        _apply_rating(meta, avg_rating, rated_count)
        common.write_note(path, meta, body)
        return "updated"
    meta = {"type": "logtag", "title": tag, "film_count": film_count, "tags": ["logtag"]}
    _apply_rating(meta, avg_rating, rated_count)
    common.write_note(path, meta, f"# {tag}")
    return "created"


def verify_links(vault: Path) -> set[str]:
    """Return the set of body wikilink targets with no matching note file."""
    existing = {p.stem for p in vault.rglob("*.md")}
    unresolved: set[str] = set()
    for folder in LINKED_FOLDERS:
        for _path, _meta, body in common.iter_folder_notes(vault, folder):
            for target in common.body_link_targets(body):
                if target not in existing:  # literal — how Obsidian/Quartz resolve
                    unresolved.add(target)
    return unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate entity stub notes.")
    parser.add_argument("--vault", type=Path, default=Path("vault"))
    parser.add_argument("--check", action="store_true", help="verify links only")
    parser.add_argument(
        "--graph-min-films",
        type=int,
        default=None,
        help="override cinegraph.yaml: apply this single film-count threshold to all "
        "entity types (entities below it are hidden from the graph, page kept)",
    )
    args = parser.parse_args()
    vault: Path = args.vault

    # Resolve visibility thresholds from cinegraph.yaml (CLI flag overrides all types).
    cfg = common.load_config(vault)
    gcfg = cfg.get("graph", {})
    mins = dict(gcfg.get("min_films") or {})
    always_show = set(gcfg.get("always_show_roles") or [])
    theme_min = int(cfg.get("themes", {}).get("min_films", 5))
    if args.graph_min_films is not None:
        mins = dict.fromkeys(("people", "studios", "genres"), args.graph_min_films)

    def hide_person(roles: set[str], film_count: int) -> bool:
        if roles & always_show:
            return False
        return film_count < mins.get("people", 2)

    def hide_simple(key: str, film_count: int) -> bool:
        return film_count < mins.get(key, 2)

    people_roles, counts, ratings = collect_entities(vault)

    if not args.check:
        tally: dict[str, int] = defaultdict(int)
        for name, roles in people_roles.items():
            n = counts["person"][name]
            avg, rc = _rating_stats(ratings["person"][name])
            tally[ensure_person(vault, name, roles, n, hide_person(roles, n), avg, rc)] += 1
        for name, n in counts["studio"].items():
            avg, rc = _rating_stats(ratings["studio"][name])
            hide = hide_simple("studios", n)
            tally[ensure_simple(vault, "Studios", name, "studio", n, hide, avg, rc)] += 1
        for name, n in counts["genre"].items():
            avg, rc = _rating_stats(ratings["genre"][name])
            hide = hide_simple("genres", n)
            tally[ensure_simple(vault, "Genres", name, "genre", n, hide, avg, rc)] += 1
        # Themes: only keywords tagging >= theme_min films become browsable pages (they
        # carry no body wikilinks, so they're never graph nodes — hide=False is moot).
        themes = {name: n for name, n in counts["theme"].items() if n >= theme_min}
        for name, n in themes.items():
            avg, rc = _rating_stats(ratings["theme"][name])
            tally[ensure_simple(vault, "Themes", name, "theme", n, False, avg, rc)] += 1
        # Log tags: every distinct diary tag gets a /logs/<tag> hub page (no threshold).
        for name, n in counts["tag"].items():
            avg, rc = _rating_stats(ratings["tag"][name])
            tally[ensure_tag(vault, name, n, avg, rc)] += 1
        print(
            f"People: {len(people_roles)} | Studios: {len(counts['studio'])} | "
            f"Genres: {len(counts['genre'])} | Themes: {len(themes)} | "
            f"Tags: {len(counts['tag'])}"
        )
        print(
            f"Stubs created={tally['created']} updated={tally['updated']} "
            f"skipped={tally['skipped']}"
        )

    unresolved = verify_links(vault)
    if unresolved:
        print(f"\n⚠ {len(unresolved)} unresolved wikilink target(s):")
        for name in sorted(unresolved):
            print(f"   - {name}")
        return 1
    print("\n✓ All body wikilinks resolve to real notes (no 'Untitled' nodes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
