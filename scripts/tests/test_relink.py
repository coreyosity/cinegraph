"""relink.py — body regeneration from frontmatter (overview + Log + Cast & crew)."""

from enrich import render_body
from relink import extract_overview


def _body(overview):
    """A film body with the log fields a relink pass would read from frontmatter."""
    return render_body(
        "Denis Villeneuve", ["Ryan Gosling"], ["Alcon"], ["Sci-Fi"], overview,
        watched="2023-02-24", rating=4.0, rewatch=True, log_tags=["cinema", "dean"],
    )


def test_extract_overview_drops_both_callouts():
    body = _body("the overview prose")
    # strips the Log callout, the Cast & crew callout, and the blank lines between them
    assert extract_overview(body) == "the overview prose"


def test_relink_round_trip_is_idempotent():
    body1 = _body("the overview prose")
    body2 = _body(extract_overview(body1) or None)  # a second relink pass
    assert body1 == body2
    assert "> [!note]- Log" in body2
    assert "> Watched 24 Feb 2023 · ★ 4.0 · Rewatch" in body2
    assert "> Tags  cinema · dean" in body2
    # Log sits between the blurb and Cast & crew
    assert body2.index("overview prose") < body2.index("[!note]- Log") < body2.index("[!info]- Cast")
