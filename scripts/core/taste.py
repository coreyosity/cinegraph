"""The taste model — one rating-weighted profile that powers BOTH Discover ranking and
Up Next watchlist predictions, plus a leave-one-out backtest that measures (and lets us
tune) its accuracy.

The profile: for each director / actor / genre / keyword, a *shrunk* average of
(rating - baseline) over the user's rated films — how much above/below their norm films
with that attribute land, pulled toward neutral when evidence is thin. `predict()` turns
that into a predicted rating for an unseen film by blending its attributes' deviations.

Pure over `list[Film]` — no vault, no I/O. The CLI (scripts/taste.py) feeds it films.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from .film import Film
from .text import canonical, theme_keywords

FIELDS = ("director", "actor", "genre", "keyword")
# How much each signal counts toward a predicted rating. Tuned against the leave-one-out
# backtest (maximising ranking correlation): themes/keywords are the most discriminative.
DEFAULT_WEIGHTS = {"director": 0.30, "keyword": 0.40, "genre": 0.20, "actor": 0.10}
TOP_N = {"actor": 3, "keyword": 5}  # blend only the strongest few; the rest are noise
SHRINK = 5  # pseudo-count: pulls low-evidence attributes toward neutral

# (field, Film attribute) for the multi-valued groups.
_MULTI = (("actor", "cast"), ("genre", "genres"), ("keyword", "keywords"))


def baseline_of(films: list[Film]) -> float:
    ratings = [f.rating for f in films if f.rating is not None]
    return round(sum(ratings) / len(ratings), 3) if ratings else 3.0


def _film_items(film: Film) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if film.director:
        items.append(("director", canonical(film.director)))
    items += [("actor", canonical(a)) for a in film.cast]
    items += [("genre", canonical(g)) for g in film.genres]
    items += [("keyword", k) for k in theme_keywords(film.keywords)]
    return items


def aggregate(films: list[Film], baseline: float):
    sums: dict[str, defaultdict[str, float]] = {f: defaultdict(float) for f in FIELDS}
    counts: dict[str, Counter[str]] = {f: Counter() for f in FIELDS}
    for film in films:
        if film.rating is None:
            continue
        dev = film.rating - baseline
        for field, name in _film_items(film):
            sums[field][name] += dev
            counts[field][name] += 1
    return sums, counts


def build_profile(films: list[Film], baseline: float, k: int = SHRINK) -> dict[str, dict]:
    sums, counts = aggregate(films, baseline)
    return {f: {n: sums[f][n] / (counts[f][n] + k) for n in sums[f]} for f in FIELDS}


def _group_devs(profile: dict, film: Film):
    """Per present group: (blended deviation, [(name, weight)…] strongest first)."""
    groups: dict[str, float] = {}
    drivers: list[tuple[str, str, float]] = []
    # director first (single value), then the multi-valued groups
    d = canonical(film.director) if film.director else None
    named = [("director", [d] if d else [])]
    for field, attr in _MULTI:
        if field == "keyword":
            names = theme_keywords(film.keywords)
        else:
            names = [canonical(x) for x in getattr(film, attr)]
        named.append((field, names))
    for field, names in named:
        if not names:
            continue
        pairs = sorted(((n, profile[field].get(n, 0.0)) for n in names), key=lambda x: x[1], reverse=True)
        top = pairs[: TOP_N[field]] if field in TOP_N else pairs
        groups[field] = sum(w for _n, w in top) / len(top)
        drivers += [(field, n, w) for n, w in pairs]
    return groups, drivers


def predict(profile: dict, baseline: float, film: Film, weights: dict = DEFAULT_WEIGHTS):
    """(predicted_rating, drivers) — drivers sorted by |weight| for explanations."""
    groups, drivers = _group_devs(profile, film)
    num = sum(weights[g] * dev for g, dev in groups.items())
    den = sum(weights[g] for g in groups)
    pred = baseline + (num / den if den else 0.0)
    drivers.sort(key=lambda d: abs(d[2]), reverse=True)
    return round(max(0.5, min(5.0, pred)), 2), drivers


def describe(drivers: list[tuple[str, str, float]]) -> str:
    """Short human reason from the strongest positive (and one strong negative) drivers."""
    pos: list[str] = []
    neg: str | None = None
    seen: set[str] = set()
    for _g, name, w in drivers:
        if w > 0.2 and name not in seen and len(pos) < 3:
            pos.append(name)
            seen.add(name)
        elif w < -0.25 and neg is None:
            neg = name
    text = "you like " + ", ".join(pos) if pos else ""
    if neg:
        text = (text + "; wary of " + neg) if text else "wary of " + neg
    return text


# --- backtest ----------------------------------------------------------------
def backtest(films: list[Film], weights: dict = DEFAULT_WEIGHTS, k: int = SHRINK) -> dict:
    """Leave-one-out: predict each rated film from all the *other* ratings, compare to
    actual. Reports MAE/RMSE and ranking correlation vs a naive (always-mean) baseline."""
    rated = [f for f in films if f.rating is not None]
    baseline = baseline_of(rated)
    sums, counts = aggregate(rated, baseline)
    rows = []  # (predicted, actual, title)
    for film in rated:
        rating = film.rating
        assert rating is not None  # rated is pre-filtered on `f.rating is not None`
        dev = rating - baseline
        loo: dict[str, dict[str, float]] = {f: {} for f in FIELDS}  # this film's attrs, itself removed
        for field, name in _film_items(film):
            c = counts[field][name] - 1
            loo[field][name] = (sums[field][name] - dev) / (c + k)
        pred, _ = predict(loo, baseline, film, weights)
        rows.append((pred, rating, film.title))
    n = len(rows)
    mae = sum(abs(p - a) for p, a, _ in rows) / n
    rmse = (sum((p - a) ** 2 for p, a, _ in rows) / n) ** 0.5
    base_mae = sum(abs(baseline - a) for _p, a, _ in rows) / n
    return {"n": n, "baseline": baseline, "mae": mae, "rmse": rmse,
            "base_mae": base_mae, "r": _pearson([p for p, _a, _ in rows], [a for _p, a, _ in rows]),
            "rows": rows}


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs) ** 0.5
    vy = sum((y - my) ** 2 for y in ys) ** 0.5
    return cov / (vx * vy) if vx and vy else 0.0


def tune(films: list[Film]):
    """Grid search over blend weights *and* shrinkage to maximise ranking correlation
    (what matters for a recommender) while keeping MAE sane."""
    weight_grid = []
    for d in (0.5, 0.4, 0.3):
        for kw in (0.4, 0.3, 0.2):
            for g in (0.2, 0.15, 0.1):
                a = round(1 - d - kw - g, 3)
                if a >= 0:
                    weight_grid.append({"director": d, "keyword": kw, "genre": g, "actor": a})
    best = (DEFAULT_WEIGHTS, SHRINK, -1.0, 1.0)
    for k in (1, 2, 3, 5):
        for w in weight_grid:
            r = backtest(films, w, k)
            if r["r"] > best[2]:
                best = (w, k, r["r"], r["mae"])
    return best  # (weights, k, r, mae)
