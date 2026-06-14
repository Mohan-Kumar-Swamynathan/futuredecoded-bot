"""Tests for Google News story search."""

from unittest.mock import MagicMock, patch

from futuredecoded.discovery.fetchers.google_news import (
    _title_overlap_score,
    search_google_news_for_story,
)


def test_title_overlap_score_prefers_related_headlines():
    score = _title_overlap_score(
        "Amazon CEO talks with U.S. officials triggered crackdown",
        "Amazon CEO met with U.S. officials before regulatory action",
    )
    assert score >= 0.3


@patch("futuredecoded.discovery.fetchers.google_news._fetch_rss_feed")
def test_search_google_news_for_story_returns_ranked_references(mock_fetch: MagicMock):
    mock_fetch.return_value = MagicMock(
        entries=[
            {
                "title": "Unrelated sports headline - ESPN",
                "link": "https://news.google.com/rss/articles/sports",
                "source": {"title": "ESPN"},
            },
            {
                "title": "Amazon CEO talks with officials - Reuters",
                "link": "https://news.google.com/rss/articles/amazon-reuters",
                "source": {"title": "Reuters"},
            },
            {
                "title": "Amazon regulatory meetings reported - Bloomberg",
                "link": "https://news.google.com/rss/articles/amazon-bloomberg",
                "source": {"title": "Bloomberg"},
            },
        ]
    )

    references = search_google_news_for_story(
        "Amazon CEO talks with U.S. officials triggered crackdown",
        limit=2,
    )

    assert len(references) == 2
    assert references[0].name == "Reuters"
    assert "amazon-reuters" in references[0].url
