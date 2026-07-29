"""verify_indexes.py — the deploy gate that catches a build shipping without data indexes."""

import json

import verify_indexes


def _write(static, name, key, rows, count=None):
    payload = {"generated": "now", "count": len(rows) if count is None else count, key: rows}
    (static / name).write_text(json.dumps(payload), encoding="utf-8")


def _all_good(static, films=2):
    rows = [{"title": f"Film {i}"} for i in range(films)]
    _write(static, "films.json", "films", rows)
    _write(static, "films-detail.json", "detail", [{"keywords": []} for _ in rows])
    _write(static, "discover.json", "recs", [{"title": "Rec"}])
    _write(static, "watchlist.json", "watchlist", [{"title": "Later"}])


def test_verify_passes_on_a_complete_build(tmp_path):
    _all_good(tmp_path)
    errors, warnings = verify_indexes.verify(tmp_path)
    assert errors == []
    assert warnings == []


def test_verify_flags_the_wiped_build(tmp_path):
    # The original bug: quartz's `rm -rf public` left contentIndex.json but took the rest.
    (tmp_path / "contentIndex.json").write_text("{}", encoding="utf-8")
    errors, _warnings = verify_indexes.verify(tmp_path)
    assert len(errors) == 4
    assert all("missing" in e for e in errors)


def test_verify_flags_a_single_missing_index(tmp_path):
    _all_good(tmp_path)
    (tmp_path / "watchlist.json").unlink()
    errors, _warnings = verify_indexes.verify(tmp_path)
    assert errors == [f"watchlist.json is missing from {tmp_path}"]


def test_verify_flags_misaligned_film_payloads(tmp_path):
    # split_detail's contract: the client only merges detail when the lengths agree, so a
    # drift here silently drops keywords/related/taste-map from every film.
    _all_good(tmp_path, films=3)
    _write(tmp_path, "films-detail.json", "detail", [{"keywords": []}])
    errors, _warnings = verify_indexes.verify(tmp_path)
    assert any("not index-aligned" in e for e in errors)


def test_verify_flags_count_mismatch(tmp_path):
    _all_good(tmp_path)
    _write(tmp_path, "films.json", "films", [{"title": "One"}, {"title": "Two"}], count=99)
    errors, _warnings = verify_indexes.verify(tmp_path)
    assert any("count=99 but 2 films rows" in e for e in errors)


def test_verify_flags_empty_films_but_only_warns_on_empty_discover(tmp_path):
    # A keyless deploy skips discover.py, so 0 recs is legitimate; 0 films never is.
    _all_good(tmp_path)
    _write(tmp_path, "discover.json", "recs", [])
    errors, warnings = verify_indexes.verify(tmp_path)
    assert errors == []
    assert warnings == ["discover.json is empty"]

    _write(tmp_path, "films.json", "films", [])
    _write(tmp_path, "films-detail.json", "detail", [])
    errors, _warnings = verify_indexes.verify(tmp_path)
    assert any("films.json is empty" in e for e in errors)


def test_verify_flags_corrupt_json(tmp_path):
    _all_good(tmp_path)
    (tmp_path / "films.json").write_text("{not json", encoding="utf-8")
    errors, _warnings = verify_indexes.verify(tmp_path)
    assert any("not valid JSON" in e for e in errors)


def test_verify_flags_wrong_shape(tmp_path):
    _all_good(tmp_path)
    (tmp_path / "discover.json").write_text('{"count":0}', encoding="utf-8")
    errors, _warnings = verify_indexes.verify(tmp_path)
    assert errors == ["discover.json has no 'recs' key"]
