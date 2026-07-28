"""ingest.py — Letterboxd CSV parsing, index building, and idempotent note writes."""

import common
import ingest


def test_parse_rating():
    assert ingest.parse_rating("4.5") == 4.5
    assert ingest.parse_rating("") is None
    assert ingest.parse_rating("   ") is None
    assert ingest.parse_rating("not a number") is None
    assert ingest.parse_rating(None) is None


def test_build_indexes_keeps_latest_diary_entry(tmp_path):
    (tmp_path / "ratings.csv").write_text(
        "Letterboxd URI,Rating\nlb/a,4.5\nlb/b,\n", encoding="utf-8"
    )
    (tmp_path / "diary.csv").write_text(
        "Letterboxd URI,Watched Date,Rewatch\n"
        "lb/a,2023-01-01,No\n"
        "lb/a,2024-02-02,Yes\n",   # later row wins (rows are chronological)
        encoding="utf-8",
    )
    ratings, diary = ingest.build_indexes(tmp_path)
    assert ratings == {"lb/a": 4.5, "lb/b": None}
    assert diary["lb/a"] == {"watched": "2024-02-02", "rewatch": True}


def test_write_film_disambiguates_duplicate_titles(tmp_path):
    used: dict[str, str] = {}
    ingest.write_film(tmp_path, "Films", used,
                      {"Name": "Dune", "Year": "1984", "Letterboxd URI": "lb/dune-1984"}, {})
    ingest.write_film(tmp_path, "Films", used,
                      {"Name": "Dune", "Year": "2021", "Letterboxd URI": "lb/dune-2021"},
                      {"rating": 5.0})
    assert (tmp_path / "Films" / "Dune.md").exists()          # first keeps the bare stem
    assert (tmp_path / "Films" / "Dune (2021).md").exists()   # second disambiguated by year


def test_write_film_preserves_enrichment_refreshes_lb_fields(tmp_path):
    row = {"Name": "Argo", "Year": "2012", "Letterboxd URI": "lb/argo"}
    ingest.write_film(tmp_path, "Films", {}, row, {"rating": 4.0})

    # Simulate a later enrich.py pass adding metadata + an overview body.
    path = tmp_path / "Films" / "Argo.md"
    meta, _ = common.read_note(path)
    meta["director"] = "Ben Affleck"
    meta["genres"] = ["Thriller"]
    common.write_note(path, meta, "overview prose")

    # Re-ingest with an updated rating + watched date.
    ingest.write_film(tmp_path, "Films", {}, row, {"rating": 4.5, "watched": "2024-01-01"})
    meta2, body2 = common.read_note(path)
    assert meta2["director"] == "Ben Affleck"      # enrichment preserved
    assert meta2["genres"] == ["Thriller"]
    assert meta2["rating"] == 4.5                    # Letterboxd-owned field refreshed
    assert meta2["watched"] == "2024-01-01"
    assert body2.strip() == "overview prose"         # body untouched
