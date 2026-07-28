"""gen_index.py — films.json record building, slug joining, theme filtering, why parsing."""

import common
import gen_index


def _film(vault, stem, **meta):
    common.write_note(vault / "Films" / f"{stem}.md", {"type": "film", **meta}, "")


def test_fallback_slug():
    assert gen_index.fallback_slug("Blade Runner 2049") == "films/blade-runner-2049"


def test_build_records_orders_joins_slugs_and_themes(tmp_path):
    _film(tmp_path, "Dune", title="Dune", year=2021, rating=5, tmdb_id=1,
          genres=["Science Fiction"], keywords=["desert", "spice"])
    _film(tmp_path, "Argo", title="Argo", year=2012, rating=4, tmdb_id=2, keywords=["heist"])
    common.write_note(tmp_path / "Themes" / "desert.md", {"type": "theme"}, "# desert")

    slugs = {"Films/Dune.md": "films/dune-2021"}   # Argo absent -> fallback
    records = gen_index.build_records(tmp_path, slugs)

    assert [r["title"] for r in records] == ["Dune", "Argo"]   # rating desc
    assert records[0]["url"] == "/films/dune-2021"             # joined from content index
    assert records[1]["url"] == "/films/argo"                  # computed fallback
    assert records[0]["themes"] == ["desert"]                  # only keywords with a Theme page
    assert records[1]["themes"] == []                          # 'heist' has no Theme page
    assert "related" in records[0]                             # similarity attached


def test_build_discover_records_flattens_why_wikilinks(tmp_path):
    common.write_note(
        tmp_path / "Discover" / "Rec.md",
        {"type": "recommendation", "title": "Rec", "year": 2000, "score": 5.0, "tmdb_id": 9},
        "**Why:** surfaced by [[Dune (2021)]] (5★); more from [[Denis Villeneuve]]\n\nsome overview",
    )
    recs = gen_index.build_discover_records(tmp_path, {})
    assert len(recs) == 1
    assert recs[0]["why"] == "surfaced by Dune (2021) (5★); more from Denis Villeneuve"


def test_build_discover_records_ignores_non_recommendations(tmp_path):
    common.write_note(tmp_path / "Discover" / "note.md", {"type": "film"}, "not a rec")
    assert gen_index.build_discover_records(tmp_path, {}) == []
