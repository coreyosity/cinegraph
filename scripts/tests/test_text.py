from core.text import KEYWORD_STOP, as_list, canonical, theme_keywords


def test_canonical_collapses_whitespace():
    assert canonical("  Denis   Villeneuve ") == "Denis Villeneuve"
    assert canonical("A\tB\nC") == "A B C"


def test_as_list_normalizes():
    assert as_list(None) == []
    assert as_list("solo") == ["solo"]
    assert as_list(["a", None, "", "b"]) == ["a", "b"]  # drops None and empty


def test_theme_keywords_drops_stopwords_and_canonicalizes():
    kws = ["aftercreditsstinger", "  grief ", "Duringcreditsstinger", "heist"]
    # stop-list removed (case-insensitive), the rest canonicalized
    assert theme_keywords(kws) == ["grief", "heist"]
    assert theme_keywords(None) == []


def test_keyword_stop_contents():
    assert "aftercreditsstinger" in KEYWORD_STOP
    assert "duringcreditsstinger" in KEYWORD_STOP
