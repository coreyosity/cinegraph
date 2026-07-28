from core.graph import _betweenness, attach_related, attach_taste_map


def _film(tmdb_id, **kw):
    base = {"tmdb_id": tmdb_id, "title": f"F{tmdb_id}", "url": f"/{tmdb_id}",
            "rating": None, "director": None, "cast": [], "genres": [],
            "studios": [], "keywords": [], "themes": [], "year": 2020}
    base.update(kw)
    return base


def test_attach_related_same_director_scores_five():
    films = [_film(1, director="D"), _film(2, director="D"), _film(3, director="E")]
    attach_related(films)
    assert films[0]["related"] == [[2, 5.0]]  # shared director -> 5.0
    assert films[2]["related"] == []          # shares nothing


def test_attach_related_cast_plus_genre_score():
    films = [_film(1, cast=["A", "B"], genres=["G"]), _film(2, cast=["A"], genres=["G"])]
    attach_related(films)
    # 1 shared cast (2.0) + 1 shared genre (0.6) = 2.6
    assert films[0]["related"] == [[2, 2.6]]


def test_betweenness_path_graph():
    # A—B—C : B lies on the only path between A and C, so it's the bridge.
    adj = {"A": {"B"}, "B": {"A", "C"}, "C": {"B"}}
    bet = _betweenness(["A", "B", "C"], adj)
    # Brandes (no undirected halving): raw 2 (counted from A and from C) x 1/((3-1)(3-2)) = 1.0
    assert bet["B"] == 1.0
    assert bet["A"] == 0.0 and bet["C"] == 0.0  # endpoints bridge nothing


def test_attach_taste_map_islands_bridges_orphans():
    films = [
        _film(1, rating=5, director="D", genres=["G"], themes=["t"]),
        _film(2, rating=4, director="D", genres=["G"], themes=["t"]),
        _film(3, rating=3, director="E", genres=["X"]),  # isolated
    ]
    attach_related(films)  # 1<->2 (director 5 + genre 0.6 = 5.6 >= 4); 3 alone
    islands = attach_taste_map(films, edge_min=4, min_island=2)

    assert len(islands) == 1 and islands[0]["size"] == 2
    assert films[0]["community"] == films[1]["community"] is not None
    assert films[2]["community"] is None
    assert films[2]["orphan"] is True and films[0]["orphan"] is False
