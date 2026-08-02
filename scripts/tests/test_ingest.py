"""ingest.py — Letterboxd CSV parsing, index building, and idempotent note writes."""

import zipfile

import common
import ingest


def test_parse_rating():
    assert ingest.parse_rating("4.5") == 4.5
    assert ingest.parse_rating("") is None
    assert ingest.parse_rating("   ") is None
    assert ingest.parse_rating("not a number") is None
    assert ingest.parse_rating(None) is None


def test_parse_tags():
    assert ingest.parse_tags("cinema, imax") == ["cinema", "imax"]
    assert ingest.parse_tags("  Cinema ,, IMAX ") == ["cinema", "imax"]  # trims, lowercases, drops blanks
    assert ingest.parse_tags("") == []
    assert ingest.parse_tags(None) == []


def test_build_indexes_keeps_latest_diary_entry_and_unions_tags(tmp_path):
    (tmp_path / "ratings.csv").write_text(
        "Letterboxd URI,Rating\nlb/a,4.5\nlb/b,\n", encoding="utf-8"
    )
    # Two diary entries for one film (a rewatch). Note the per-entry URIs differ from any
    # film URI — the diary is keyed by (Name, Year), not by URI.
    (tmp_path / "diary.csv").write_text(
        "Name,Year,Letterboxd URI,Watched Date,Rewatch,Tags\n"
        'Dune,2021,lb/entry-1,2023-01-01,No,"cinema, first-watch"\n'
        'Dune,2021,lb/entry-2,2024-02-02,Yes,"cinema, imax"\n',   # later row wins for watched/rewatch
        encoding="utf-8",
    )
    ratings, diary = ingest.build_indexes(tmp_path)
    assert ratings == {"lb/a": 4.5, "lb/b": None}
    assert diary[("Dune", "2021")] == {
        "watched": "2024-02-02",       # latest entry
        "rewatch": True,
        "log_tags": ["cinema", "first-watch", "imax"],   # unioned across both entries, deduped
    }


def test_build_indexes_omits_log_tags_when_absent(tmp_path):
    # An export with no Tags column (older exports) must not add a log_tags key.
    (tmp_path / "diary.csv").write_text(
        "Name,Year,Letterboxd URI,Watched Date,Rewatch\nDune,2021,lb/e,2023-01-01,No\n",
        encoding="utf-8",
    )
    _, diary = ingest.build_indexes(tmp_path)
    assert diary[("Dune", "2021")] == {"watched": "2023-01-01", "rewatch": False}


def test_ingest_joins_diary_by_name_year_not_uri(tmp_path, monkeypatch):
    """Regression: diary.csv's URI is the per-entry permalink, so watched date / rewatch /
    log_tags must join to the film by (Name, Year). Here the diary URI deliberately differs
    from the film URI — a URI join would silently drop all three."""
    export = tmp_path / "export"
    export.mkdir()
    vault = tmp_path / "vault"
    (export / "watched.csv").write_text(
        "Date,Name,Year,Letterboxd URI\n"
        "2022-07-07,The Mauritanian,2021,https://boxd.it/film\n",
        encoding="utf-8",
    )
    (export / "ratings.csv").write_text(
        "Letterboxd URI,Rating\nhttps://boxd.it/film,4.0\n", encoding="utf-8"
    )
    (export / "diary.csv").write_text(
        "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
        '2022-07-07,The Mauritanian,2021,https://boxd.it/entry,4.0,Yes,"dad, prime",2022-07-06\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv", ["ingest.py", "--export", str(export), "--vault", str(vault)]
    )
    assert ingest.main() == 0

    meta, _ = common.read_note(vault / "Films" / "The Mauritanian.md")
    assert meta["watched"] == "2022-07-06"    # diary Watched Date, NOT watched.csv Date
    assert meta["rewatch"] is True
    assert meta["log_tags"] == ["dad", "prime"]
    assert meta["rating"] == 4.0


def test_ingest_accepts_zip(tmp_path, monkeypatch):
    """A user can point --export straight at the Letterboxd .zip; ingest extracts it to a
    temp dir (auto-cleaned) and writes notes exactly as it would from an unzipped folder."""
    export = tmp_path / "letterboxd-export.zip"
    with zipfile.ZipFile(export, "w") as zf:
        zf.writestr(
            "watched.csv", "Date,Name,Year,Letterboxd URI\n2022-07-07,Dune,2021,lb/dune\n"
        )
        zf.writestr("ratings.csv", "Letterboxd URI,Rating\nlb/dune,4.5\n")
        zf.writestr("watchlist.csv", "Name,Year,Letterboxd URI\nArrival,2016,lb/arrival\n")
    vault = tmp_path / "vault"
    monkeypatch.setattr(
        "sys.argv", ["ingest.py", "--export", str(export), "--vault", str(vault)]
    )
    assert ingest.main() == 0

    meta, _ = common.read_note(vault / "Films" / "Dune.md")
    assert meta["rating"] == 4.5
    assert (vault / "Watchlist" / "Arrival.md").exists()


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


def test_write_film_writes_and_refreshes_log_tags(tmp_path):
    row = {"Name": "Dune", "Year": "2021", "Letterboxd URI": "lb/dune"}
    ingest.write_film(tmp_path, "Films", {}, row, {"log_tags": ["cinema", "imax"]})
    path = tmp_path / "Films" / "Dune.md"
    meta, _ = common.read_note(path)
    assert meta["log_tags"] == ["cinema", "imax"]

    # Re-ingest with a changed tag set → refreshed (it's a Letterboxd-owned field).
    ingest.write_film(tmp_path, "Films", {}, row, {"log_tags": ["cinema", "rewatch"]})
    meta2, _ = common.read_note(path)
    assert meta2["log_tags"] == ["cinema", "rewatch"]
