"""gen_entities.py — entity collection, taste stats, graph-visibility markers, link check."""

import common
import gen_entities


def _film(vault, folder, stem, **meta):
    common.write_note(vault / folder / f"{stem}.md", {"type": "film", **meta}, "")


def test_collect_entities_counts_roles_and_ratings(tmp_path):
    _film(tmp_path, "Films", "A", director="D", cast=["X", "Y"], genres=["G"],
          studios=["S"], keywords=["grief", "aftercreditsstinger"], rating=4)
    _film(tmp_path, "Films", "B", director="D", cast=["X"], genres=["G", "H"], rating=2)
    _film(tmp_path, "Watchlist", "W", director="WD", cast=["WX"], studios=["WS"], genres=["WG"])

    people_roles, counts, ratings = gen_entities.collect_entities(tmp_path)

    assert people_roles["D"] == {"director"}
    assert people_roles["X"] == {"actor"}
    assert people_roles["WD"] == {"director"}          # watchlist people still get roles
    assert counts["person"]["D"] == 2 and counts["person"]["Y"] == 1
    assert counts["person"]["WD"] == 0                  # watchlist-only -> not "watched"
    assert counts["studio"]["S"] == 1 and counts["studio"]["WS"] == 0   # WS registered at 0
    assert counts["genre"]["G"] == 2 and counts["genre"]["WG"] == 0
    assert counts["theme"]["grief"] == 1               # stop-listed keyword excluded
    assert "aftercreditsstinger" not in counts["theme"]
    assert sorted(ratings["person"]["D"]) == [2.0, 4.0]
    assert sorted(ratings["genre"]["G"]) == [2.0, 4.0]


def test_rating_stats():
    assert gen_entities._rating_stats([4.0, 5.0]) == (4.5, 2)
    assert gen_entities._rating_stats([]) == (None, 0)


def test_apply_visibility_toggles_both_graph_markers():
    meta = {"tags": ["person", "director"]}
    gen_entities._apply_visibility(meta, hide=True)
    assert meta["unlisted"] is True and "graph-hide" in meta["tags"]

    gen_entities._apply_visibility(meta, hide=False)
    assert "unlisted" not in meta and "graph-hide" not in meta["tags"]


def test_ensure_person_merges_roles_idempotently(tmp_path):
    gen_entities.ensure_person(tmp_path, "D", {"director"}, 3, False, 4.2, 3)
    status = gen_entities.ensure_person(tmp_path, "D", {"actor"}, 4, False, 4.0, 4)
    assert status == "updated"
    meta, _ = common.read_note(tmp_path / "People" / "D.md")
    assert meta["roles"] == ["actor", "director"]    # merged, sorted
    assert meta["film_count"] == 4                    # refreshed
    assert meta["tags"] == ["person", "actor", "director"]


def test_verify_links_flags_unresolved(tmp_path):
    common.write_note(tmp_path / "Films" / "A.md", {"type": "film"}, "see [[Denis]] and [[Missing]]")
    common.write_note(tmp_path / "People" / "Denis.md", {"type": "person"}, "# Denis")
    unresolved = gen_entities.verify_links(tmp_path)
    assert unresolved == {"Missing"}                  # Denis resolves, Missing doesn't
