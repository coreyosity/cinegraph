from core.recommend import W_DIRECTOR, score_candidate, seed_affinity


def test_seed_affinity():
    assert seed_affinity([("s1", 5.0), ("s2", 4.0)], 4.0) == 1.0  # (5-4)+(4-4)


def test_score_candidate_director_match():
    profile = {"director": {"D": 1.0}, "actor": {}, "genre": {}, "keyword": {}}
    r = score_candidate(profile, "D", cast=[], genres=[], keywords=[], affinity=0.0, vote=6.0)
    assert r is not None
    assert r["score"] == W_DIRECTOR * 1.0   # 2.0; genre/graph/vote terms all zero here
    assert r["why_director"] == "D"
    assert r["why_actor"] is None


def test_score_candidate_gated_when_no_match():
    empty: dict[str, dict] = {"director": {}, "actor": {}, "genre": {}, "keyword": {}}
    assert score_candidate(empty, "Unknown", ["X"], ["Y"], ["Z"], 5.0, 8.0) is None


def test_score_candidate_gated_on_disliked_director():
    profile = {"director": {"D": -1.0}, "actor": {}, "genre": {}, "keyword": {}}
    # content = 2.0 * -1.0 = -2.0 <= 0 -> gated
    assert score_candidate(profile, "D", [], [], [], 0.0, 6.0) is None
