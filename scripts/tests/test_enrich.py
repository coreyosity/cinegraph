"""enrich.py — build_note metadata assembly (movie + tv paths), no network."""

import enrich


def _movie_data():
    return {
        "id": 335984,
        "title": "Blade Runner 2049",
        "release_date": "2017-10-04",
        "runtime": 164,
        "original_language": "en",
        "poster_path": "/poster.jpg",
        "overview": "A young blade runner uncovers a secret.",
        "genres": [{"name": "Science Fiction"}, {"name": "Drama"}],
        "production_companies": [{"name": "Alcon Entertainment"}, {"name": "Warner Bros."}],
        "production_countries": [{"name": "United States", "iso_3166_1": "us"}],
        "credits": {
            "crew": [{"job": "Writer", "name": "Hampton Fancher"},
                     {"job": "Director", "name": "Denis Villeneuve"}],
            "cast": [{"name": "Ryan Gosling"}, {"name": "Ana de Armas"}, {"name": "Harrison Ford"}],
        },
        "keywords": {"keywords": [{"name": "dystopia"}, {"name": "artificial intelligence"}]},
    }


def test_build_note_movie_core_fields():
    meta = {"title": "Blade Runner 2049", "year": 2017, "rating": 4.5,
            "watched": "2023-05-12", "letterboxd": "https://letterboxd.com/film/x/"}
    m, _ = enrich.build_note(meta, _movie_data(), "movie", cast_size=2)

    assert m["type"] == "film" and m["content_type"] == "movie"
    assert m["title"] == "Blade Runner 2049" and m["year"] == 2017
    assert m["director"] == "Denis Villeneuve"          # picked from crew by job
    assert m["cast"] == ["Ryan Gosling", "Ana de Armas"]  # truncated to cast_size
    assert m["genres"] == ["Science Fiction", "Drama"]
    assert m["studios"] == ["Alcon Entertainment", "Warner Bros."]
    assert m["keywords"] == ["dystopia", "artificial intelligence"]
    assert m["runtime"] == 164 and m["language"] == "en"
    assert m["country"] == "United States" and m["country_code"] == "US"  # code upper-cased
    assert m["poster"] == "https://image.tmdb.org/t/p/w500/poster.jpg"


def test_build_note_preserves_letterboxd_owned_and_extras():
    meta = {"title": "X", "year": 2017, "rating": 4.5, "watched": "2023-05-12",
            "letterboxd": "https://letterboxd.com/film/x/", "tags": ["film", "fav"]}
    m, _ = enrich.build_note(meta, _movie_data(), "movie", cast_size=10)
    assert m["rating"] == 4.5 and m["watched"] == "2023-05-12"  # never overwritten
    assert m["letterboxd"] == "https://letterboxd.com/film/x/"  # unknown extra kept
    assert m["tags"] == ["film", "fav"]                          # existing tags preserved


def test_build_note_key_order_is_stable():
    m, _ = enrich.build_note({"title": "X"}, _movie_data(), "movie", cast_size=10)
    keys = [k for k in m if k in enrich.FILM_KEY_ORDER]
    assert keys == [k for k in enrich.FILM_KEY_ORDER if k in m]  # ordered subset, no shuffle
    assert next(iter(m)) == "type"


def test_build_note_body_has_overview_and_wikilinks():
    _, body = enrich.build_note({"title": "X"}, _movie_data(), "movie", cast_size=2)
    assert "A young blade runner" in body
    assert "[[Denis Villeneuve]]" in body
    assert "> [!info]- Cast & crew" in body   # links tucked in a folded callout
    assert "[!note]- Log" not in body          # no diary fields -> no Log callout


def test_fmt_date():
    assert enrich.fmt_date("2023-02-24") == "24 Feb 2023"
    assert enrich.fmt_date("2023-12-01T09:00") == "1 Dec 2023"   # trailing time ignored
    assert enrich.fmt_date("sometime") == "sometime"              # unparseable -> raw


def test_render_log_full_partial_and_empty():
    assert enrich.render_log("2023-02-24", 4.0, True, ["cinema", "dean"]) == (
        "> [!note]- Log\n"
        "> Watched 24 Feb 2023 · ★ 4.0 · Rewatch\n"
        "> Tags  cinema · dean"
    )
    # no rating, not a rewatch -> just the watched date
    assert enrich.render_log("2023-02-24", None, False, []) == (
        "> [!note]- Log\n> Watched 24 Feb 2023"
    )
    # tags only (no diary entry) -> just the tags line
    assert enrich.render_log(None, None, False, ["home"]) == (
        "> [!note]- Log\n> Tags  home"
    )
    assert enrich.render_log(None, None, False, None) is None  # nothing logged


def test_build_note_body_has_log_callout_when_logged():
    meta = {"title": "X", "watched": "2023-05-12", "rating": 4.5,
            "rewatch": True, "log_tags": ["cinema", "dean"]}
    _, body = enrich.build_note(meta, _movie_data(), "movie", cast_size=2)
    assert "> [!note]- Log" in body
    assert "> Watched 12 May 2023 · ★ 4.5 · Rewatch" in body
    assert "> Tags  cinema · dean" in body
    # order: overview, then Log, then Cast & crew
    assert body.index("young blade runner") < body.index("[!note]- Log") < body.index("[!info]- Cast")


def test_build_note_tv_uses_created_by_and_origin_country():
    meta = {"title": "Black Mirror", "year": 2011}
    data = {
        "id": 42009,
        "name": "Black Mirror",
        "first_air_date": "2011-12-04",
        "episode_run_time": [60],
        "original_language": "en",
        "poster_path": None,
        "genres": [{"name": "Sci-Fi & Fantasy"}],
        "production_companies": [{"name": "House of Tomorrow"}],
        "production_countries": [],          # TV often exposes only origin_country
        "origin_country": ["GB"],
        "created_by": [{"name": "Charlie Brooker"}],
        "credits": {"cast": [{"name": "Actor A"}], "crew": []},
        "keywords": {"results": [{"name": "anthology"}]},  # tv keywords live under "results"
    }
    m, _ = enrich.build_note(meta, data, "tv", cast_size=10)
    assert m["content_type"] == "tv"
    assert m["director"] == "Charlie Brooker"     # created_by, not crew
    assert m["runtime"] == 60                       # episode_run_time[0]
    assert m["year"] == 2011                         # from first_air_date
    assert m["keywords"] == ["anthology"]
    assert m["country_code"] == "GB" and m["country"] == "GB"  # origin_country fallback
    assert "poster" not in m   # None-valued fields (posterless title) are dropped, not written null


def test_build_note_year_falls_back_when_release_missing():
    data = {**_movie_data(), "release_date": ""}
    m, _ = enrich.build_note({"title": "X", "year": 1999}, data, "movie", cast_size=10)
    assert m["year"] == 1999


def test_resolve_target_cached_needs_no_network():
    # tmdb_id present -> returns immediately without touching the session.
    assert enrich.resolve_target(None, "key", {"tmdb_id": 335984}) == ("movie", 335984, "cached")
    assert enrich.resolve_target(
        None, "key", {"tmdb_id": 42009, "content_type": "tv"}
    ) == ("tv", 42009, "cached")


def test_load_key_prefers_cli_then_env(monkeypatch):
    assert enrich.load_key("cli-key") == "cli-key"
    monkeypatch.setenv("TMDB_KEY", "env-key")
    assert enrich.load_key(None) == "env-key"
