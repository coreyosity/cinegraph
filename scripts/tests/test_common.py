"""common.py — frontmatter round-trip, filename/link normalization, config merge."""

import common


def test_note_round_trip(tmp_path):
    meta = {"type": "film", "title": "X", "year": 2020, "genres": ["A", "B"], "rating": 4.5}
    body = "an overview\n\n> [!info]- Cast & crew\n> **Director** [[D]]"
    path = tmp_path / "Films" / "X.md"
    common.write_note(path, meta, body)
    read_meta, read_body = common.read_note(path)
    assert read_meta == meta          # frontmatter survives verbatim
    assert read_body.strip() == body  # body survives (modulo framing newlines)


def test_read_note_missing_frontmatter(tmp_path):
    path = tmp_path / "plain.md"
    path.write_text("no frontmatter here", encoding="utf-8")
    assert common.read_note(path) == ({}, "no frontmatter here")


def test_dump_note_empty_body_has_no_trailing_blank():
    text = common.dump_note({"type": "person"}, "")
    assert text == "---\ntype: person\n---\n"


def test_link_name_strips_reserved_and_trailing_dot():
    assert common.link_name("Warner Bros.") == "Warner Bros"   # trailing dot (Windows-hostile)
    assert common.link_name("Face/Off") == "FaceOff"           # path separator removed
    assert common.link_name("A: B") == "A B"                   # reserved ':' removed, spaces collapse
    assert common.link_name("Who? [x]#y") == "Who xy"          # ? [ ] # all stripped
    assert common.link_name("   ") == "untitled"               # empties fall back


def test_wikilink_matches_link_name():
    assert common.wikilink("Warner Bros.") == "[[Warner Bros]]"


def test_body_link_targets_extracts_plain_and_aliased():
    body = "see [[Denis Villeneuve]] and [[Ryan Gosling|Gos]] here"
    assert common.body_link_targets(body) == {"Denis Villeneuve", "Ryan Gosling"}


def test_load_config_defaults_when_absent(tmp_path):
    cfg = common.load_config(tmp_path / "vault")  # no cinegraph.yaml alongside
    assert cfg["graph"]["min_films"]["people"] == 2
    assert cfg["themes"]["min_films"] == 5


def test_load_config_deep_merges_over_defaults(tmp_path):
    (tmp_path / "cinegraph.yaml").write_text(
        "themes:\n  min_films: 10\ngraph:\n  min_films:\n    people: 3\n", encoding="utf-8"
    )
    cfg = common.load_config(tmp_path / "vault")
    assert cfg["themes"]["min_films"] == 10               # overridden
    assert cfg["graph"]["min_films"]["people"] == 3       # overridden (nested)
    assert cfg["graph"]["min_films"]["studios"] == 2      # untouched default preserved
    assert cfg["graph"]["always_show_roles"] == ["director"]
