"""Film-similarity graph + taste islands — the pure graph analytics.

`attach_related` scores each film's most-similar films (the edges that power both the
"Related films" section and the constellation). `attach_taste_map` partitions that graph
into named 'islands' (weighted label propagation + distinctiveness naming), flags bridge
films (Brandes betweenness) and orphans. Both operate on a passed-in list of film record
dicts and mutate them in place — no vault, no I/O. The record shape is the `Film` fields
plus `url` and the computed `related`/`community`/`bridge`/`orphan`/`themes`.
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict, deque

from .text import theme_keywords


def attach_related(films: list[dict], top_n: int = 10) -> None:
    """Precompute each film's most similar films (shared director/cast/keywords/genres)
    and store them as `related: [[tmdb_id, score], ...]`. This one similarity definition
    powers *both* the film-page "Related films" section and the film-constellation graph.

    Candidates are drawn from films sharing a director/actor/keyword (via an inverted
    index) — genre alone is too broad — then scored; genre overlap still adds to the score.
    """
    index: dict[str, dict] = {"director": defaultdict(list), "cast": defaultdict(list),
                              "keyword": defaultdict(list)}
    sets = []
    for i, f in enumerate(films):
        cast, kws, gens = set(f["cast"]), set(theme_keywords(f["keywords"])), set(f["genres"])
        sets.append((f.get("director"), cast, kws, gens))
        if f.get("director"):
            index["director"][f["director"]].append(i)
        for c in cast:
            index["cast"][c].append(i)
        for k in kws:
            index["keyword"][k].append(i)

    for i, f in enumerate(films):
        di, ci, ki, gi = sets[i]
        candidates: set[int] = set()
        if di:
            candidates.update(index["director"][di])
        for c in ci:
            candidates.update(index["cast"][c])
        for k in ki:
            candidates.update(index["keyword"][k])
        candidates.discard(i)

        scored = []
        for j in candidates:
            if films[j].get("tmdb_id") is None:
                continue
            dj, cj, kj, gj = sets[j]
            score = 5.0 if di and di == dj else 0.0
            score += 2 * len(ci & cj) + 1.2 * len(ki & kj) + 0.6 * len(gi & gj)
            if score > 0:
                scored.append((score, films[j]["tmdb_id"]))
        scored.sort(reverse=True)
        f["related"] = [[tid, round(s, 1)] for s, tid in scored[:top_n]]


# --- Taste map: islands (communities), bridges (betweenness), orphans -------------
def _tags(f: dict) -> list[tuple[str, str]]:
    """The taggable attributes of a film, used to *name* an island by distinctiveness."""
    tags = [("genre", g) for g in f.get("genres") or []]
    tags += [("theme", k) for k in f.get("themes") or []]
    tags += [("studio", s) for s in (f.get("studios") or [])[:3]]
    if f.get("director"):
        tags.append(("director", f["director"]))
    if f.get("year"):
        tags.append(("decade", f"{f['year'] // 10 * 10}s"))
    return tags


def _betweenness(nodes: list, adj: dict) -> dict:
    """Brandes' betweenness centrality (unweighted) — how often a film sits on the
    shortest path between others; high = a bridge between your taste-worlds."""
    cb = dict.fromkeys(nodes, 0.0)
    for s in nodes:
        stack, pred = [], defaultdict(list)
        sigma = dict.fromkeys(nodes, 0.0); sigma[s] = 1.0
        dist = dict.fromkeys(nodes, -1); dist[s] = 0
        q = deque([s])
        while q:
            v = q.popleft(); stack.append(v)
            for w in adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1; q.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]; pred[w].append(v)
        delta = dict.fromkeys(nodes, 0.0)
        while stack:
            w = stack.pop()
            for v in pred[w]:
                delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                cb[w] += delta[w]
    n = len(nodes)
    scale = 1 / ((n - 1) * (n - 2)) if n > 2 else 1.0
    return {v: cb[v] * scale for v in nodes}


def attach_taste_map(films: list[dict], edge_min: int = 4, min_island: int = 6) -> list[dict]:
    """Partition the film-similarity graph into named 'islands' (weighted label
    propagation + distinctiveness naming), mark bridge films (betweenness) and orphans.
    Attaches `community`/`bridge`/`orphan` per film; returns the islands metadata."""
    byid = {f["tmdb_id"]: f for f in films if f.get("tmdb_id") is not None}
    adj_w, adj = defaultdict(list), defaultdict(set)
    for f in films:
        tid = f.get("tmdb_id")
        if tid is None:
            continue
        for rid, w in f.get("related", []):
            if w >= edge_min and rid in byid:
                adj_w[tid].append((rid, w)); adj_w[rid].append((tid, w))
                adj[tid].add(rid); adj[rid].add(tid)
    active = [i for i in byid if adj[i]]

    label = {i: i for i in byid}
    rng = random.Random(1)
    for _ in range(30):
        rng.shuffle(active); changed = 0
        for n in active:
            c: defaultdict[int, float] = defaultdict(float)
            for nb, w in adj_w[n]:
                c[label[nb]] += w
            best = max(c, key=lambda lab: (c[lab], -lab))
            if label[n] != best:
                label[n] = best; changed += 1
        if not changed:
            break

    groups = defaultdict(list)
    for n in active:
        groups[label[n]].append(n)

    total = len(films)
    glob: Counter[tuple[str, str]] = Counter()
    for f in films:
        for t in set(_tags(f)):
            glob[t] += 1

    islands: list[dict] = []
    for members in sorted(groups.values(), key=len, reverse=True):
        if len(members) < min_island:
            continue
        size = len(members)
        inc: Counter[tuple[str, str]] = Counter()
        for i in members:
            for t in set(_tags(byid[i])):
                inc[t] += 1
        scored = sorted(
            ((ci * math.log(total / glob[t]), t[1]) for t, ci in inc.items()
             if ci >= max(3, 0.2 * size)),
            reverse=True,
        )
        names, seen = [], set()
        for _s, nm in scored:
            if nm not in seen:
                names.append(nm); seen.add(nm)
            if len(names) == 3:
                break
        iid = len(islands)
        for i in members:
            byid[i]["community"] = iid
        examples = sorted((byid[i] for i in members),
                          key=lambda f: f.get("rating") or 0, reverse=True)[:4]
        islands.append({
            "id": iid, "name": " · ".join(names) if names else "mixed", "size": size,
            "examples": [{"title": e["title"], "url": e["url"]} for e in examples],
        })

    bet = _betweenness(active, adj) if active else {}
    for f in films:
        tid = f.get("tmdb_id")
        f.setdefault("community", None)
        f["bridge"] = round(bet.get(tid, 0.0), 5)
        f["orphan"] = tid is not None and not adj[tid]
    return islands
