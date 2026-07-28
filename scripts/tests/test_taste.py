import pytest

from core.film import Film
from core.taste import (
    DEFAULT_WEIGHTS,
    backtest,
    baseline_of,
    build_profile,
    describe,
    predict,
)


def two_films():
    # A rated 5, B rated 3 -> baseline 4.0. Director D appears in both (cancels out).
    return [
        Film.from_note({"title": "A", "rating": 5, "director": "D",
                        "genres": ["G"], "cast": ["C1"], "keywords": ["K"]}),
        Film.from_note({"title": "B", "rating": 3, "director": "D",
                        "genres": ["G2"], "cast": ["C2"]}),
    ]


def test_baseline_of():
    assert baseline_of(two_films()) == 4.0


def test_build_profile_shrunk_deviations():
    p = build_profile(two_films(), 4.0, k=5)
    # director D: (+1 from A) + (-1 from B) = 0, count 2 -> 0/(2+5)
    assert p["director"]["D"] == 0.0
    # genre G: +1 dev, count 1 -> 1/(1+5); G2: -1 -> -1/6
    assert p["genre"]["G"] == pytest.approx(1 / 6)
    assert p["genre"]["G2"] == pytest.approx(-1 / 6)
    assert p["actor"]["C1"] == pytest.approx(1 / 6)


def test_predict_hand_computed():
    p = build_profile(two_films(), 4.0, k=5)
    film = Film.from_note({"director": "D", "genres": ["G"], "cast": ["C1"], "keywords": ["K"]})
    pred, drivers = predict(p, 4.0, film, DEFAULT_WEIGHTS)
    # groups present: director(0), genre(1/6), actor(1/6), keyword(1/6); den = sum of all weights = 1.0
    # num = 0.30*0 + 0.20*(1/6) + 0.10*(1/6) + 0.40*(1/6) = 0.70/6 -> pred = 4.0 + 0.11667 = 4.12
    assert pred == 4.12
    assert any(name == "G" for _g, name, _w in drivers)


def test_describe_positive_and_negative_drivers():
    drivers = [("genre", "LovedGenre", 0.5), ("keyword", "BadTheme", -0.4), ("actor", "Meh", 0.05)]
    assert describe(drivers) == "you like LovedGenre; wary of BadTheme"
    assert describe([("actor", "Meh", 0.05)]) == ""  # nothing strong enough


def test_backtest_report_shape():
    r = backtest(two_films())
    assert r["n"] == 2
    for key in ("mae", "rmse", "r", "baseline", "base_mae", "rows"):
        assert key in r
