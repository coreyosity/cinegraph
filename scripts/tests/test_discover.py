"""discover.py — exclusion collection, seed selection, and the watchlist-key normalizer."""

import common
import discover


def _film(vault, folder, stem, **meta):
    common.write_note(vault / folder / f"{stem}.md", {"type": "film", **meta}, "")


def test_norm_key_normalizes_title_and_year():
    assert discover.norm_key("Blade Runner", 2049) == ("blade runner", "2049")
    assert discover.norm_key("Warner Bros.", None) == ("warner bros", "")  # link_name normalizes
    assert discover.norm_key("", None) == ("untitled", "")                 # empty -> link_name fallback


def test_collect_exclusions(tmp_path):
    _film(tmp_path, "Films", "A", title="A", tmdb_id=1)
    _film(tmp_path, "Films", "B", title="B", tmdb_id=2)
    _film(tmp_path, "Watchlist", "Foo", title="Foo", year=2000)
    common.write_note(tmp_path / "Discover" / "_dismissed" / "X.md",
                      {"type": "recommendation", "tmdb_id": 99}, "")
    common.write_note(tmp_path / "Discover" / "Y.md",
                      {"type": "recommendation", "tmdb_id": 50, "dismissed": True}, "")

    watched, watchlist, dismissed = discover.collect_exclusions(tmp_path)
    assert watched == {1, 2}
    assert discover.norm_key("Foo", 2000) in watchlist
    assert dismissed == {99, 50}         # both the _dismissed/ folder and the dismissed: true flag


def test_pick_seeds_filters_by_rating_skips_tv_and_sorts(tmp_path):
    _film(tmp_path, "Films", "Top", rating=5, tmdb_id=1)
    _film(tmp_path, "Films", "Good", rating=4.5, tmdb_id=2)
    _film(tmp_path, "Films", "Mid", rating=3, tmdb_id=3)                       # below seed_min
    _film(tmp_path, "Films", "Show", rating=5, tmdb_id=4, content_type="tv")   # tv excluded

    seeds = discover.pick_seeds(None, tmp_path, seed_min=4.0, max_seeds=10)
    assert [tmdb_id for tmdb_id, *_ in seeds] == [1, 2]   # rating desc; Mid & Show excluded


def test_pick_seeds_respects_max_seeds(tmp_path):
    for i in range(5):
        _film(tmp_path, "Films", f"F{i}", rating=5, tmdb_id=i)
    assert len(discover.pick_seeds(None, tmp_path, seed_min=4.0, max_seeds=3)) == 3
