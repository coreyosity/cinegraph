from core.film import Film


def test_from_note_normalizes_lists_and_rating():
    f = Film.from_note({
        "title": "X", "rating": 4, "director": "D",
        "cast": "Solo Actor", "genres": ["Drama", "Sci-Fi"], "tmdb_id": 42,
    })
    assert f.title == "X" and f.tmdb_id == 42
    assert f.rating == 4.0 and isinstance(f.rating, float)  # int coerced to float
    assert f.cast == ["Solo Actor"]                          # scalar -> list
    assert f.genres == ["Drama", "Sci-Fi"]
    assert f.director == "D"


def test_from_note_defaults_when_missing():
    f = Film.from_note({})
    assert f.rating is None and f.director is None
    assert f.cast == [] and f.genres == [] and f.keywords == []


def test_from_note_non_numeric_rating_is_none():
    assert Film.from_note({"rating": "★★★"}).rating is None
    assert Film.from_note({"director": ""}).director is None  # falsy -> None
