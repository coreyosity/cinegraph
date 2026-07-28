"""Recommendation scoring — how well an unseen candidate matches the taste profile.

Pure ranking math: given a candidate's attributes + the taste profile, returns a score
and the human 'why', or None if it fails the taste gate. The candidate *fetching* (TMDB)
stays in the app layer (scripts/discover.py) — this is just the scoring, reusable per user.
"""

from __future__ import annotations

from .text import canonical

# Content (a director/actor/keyword you rate highly) is the meaningful signal and outranks
# TMDB's own "similar" graph; genres are averaged (not summed) so multi-genre films don't
# inflate. Tune to taste.
W_DIRECTOR, W_ACTOR, W_KEYWORD = 2.0, 0.8, 0.3
W_GENRE, W_GRAPH, W_VOTE = 0.6, 0.4, 0.2


def seed_affinity(seeds, baseline: float) -> float:
    """Sum of (rating - baseline) over the loved films that surfaced this candidate."""
    return sum(rating - baseline for _stem, rating in seeds)


def score_candidate(profile: dict, director, cast, genres, keywords, affinity: float, vote: float):
    """Score an unseen candidate against the taste profile. Returns a dict with `score`
    and the `why_*` components, or None if it fails the taste gate (no specific match)."""
    dir_w = profile["director"].get(canonical(director or ""), 0)
    actor_ranked = sorted(
        ((a, profile["actor"].get(canonical(a), 0)) for a in cast),
        key=lambda x: x[1], reverse=True,
    )
    best_actor, actor_w = actor_ranked[0] if actor_ranked else (None, 0)
    kw_ranked = sorted(
        ((k, profile["keyword"].get(canonical(k), 0)) for k in keywords),
        key=lambda x: x[1], reverse=True,
    )
    kw_w = sum(w for _k, w in kw_ranked[:5])  # only the strongest thematic matches
    gen_scores = [profile["genre"].get(canonical(g), 0) for g in genres]
    gen_w = sum(gen_scores) / len(gen_scores) if gen_scores else 0

    # content = specific, meaningful overlap with your taste
    content = W_DIRECTOR * dir_w + W_ACTOR * max(actor_w, 0) + W_KEYWORD * kw_w
    if content <= 0:  # gate — require a real taste match, not just TMDB's graph
        return None
    final = content + W_GENRE * gen_w + W_GRAPH * affinity + W_VOTE * (vote - 6)
    return {
        "score": final,
        "why_director": director if dir_w > 0 else None,
        "why_actor": best_actor if actor_w > 0 else None,
        "why_genres": [g for g, s in zip(genres, gen_scores, strict=True) if s > 0][:3],
        "why_keywords": [k for k, w in kw_ranked if w > 0][:3],
    }
