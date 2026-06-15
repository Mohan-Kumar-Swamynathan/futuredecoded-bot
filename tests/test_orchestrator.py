"""Tests for orchestrator story retry logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from futuredecoded.config.channel_profile import ContentFormat
from futuredecoded.discovery.virality_scorer import ScoredStory
from futuredecoded.editorial.fact_checker import FactCheckResult
from futuredecoded.pipeline.orchestrator import run_daily_pipeline


def _make_story(title: str, score: float, source: str = "google_news") -> ScoredStory:
    return ScoredStory(
        title=title,
        url=f"https://example.com/{title.replace(' ', '-').lower()}",
        source=source,
        trend_score=score,
        virality_score=score,
        curiosity_score=score,
        search_potential_score=score,
        monetization_score=score,
        viral_probability=score,
        competition=20.0,
        search_growth="80%",
        recommended_format="both",
        priority="high",
        content_hash=f"hash-{title}",
    )


@patch("futuredecoded.pipeline.orchestrator.analyse_and_update_preferences")
@patch("futuredecoded.pipeline.orchestrator.generate_weekly_report")
@patch("futuredecoded.pipeline.orchestrator._persist_story")
@patch("futuredecoded.pipeline.orchestrator.store_analytics_snapshot")
@patch("futuredecoded.pipeline.orchestrator.upload_video")
@patch("futuredecoded.pipeline.orchestrator.publish_social_posts")
@patch("futuredecoded.pipeline.orchestrator.build_short_video", return_value=Path("short.mp4"))
@patch("futuredecoded.pipeline.orchestrator.build_long_video", return_value=Path("long.mp4"))
@patch("futuredecoded.pipeline.orchestrator.synthesise_voice")
@patch("futuredecoded.pipeline.orchestrator.collect_visuals_for_story", return_value=[Path("img.jpg")])
@patch("futuredecoded.pipeline.orchestrator.enrich_seo")
@patch("futuredecoded.pipeline.orchestrator.generate_scripts")
@patch("futuredecoded.pipeline.orchestrator.gather_research")
@patch("futuredecoded.pipeline.orchestrator.decide_format")
@patch("futuredecoded.pipeline.orchestrator.verify_story")
@patch("futuredecoded.pipeline.orchestrator.discover_ranked_stories")
@patch("futuredecoded.pipeline.orchestrator.init_database")
@patch("futuredecoded.pipeline.orchestrator.get_settings")
def test_run_daily_pipeline_retries_until_fact_check_passes(
    mock_settings,
    _mock_init_db,
    mock_discover,
    mock_verify,
    mock_decide_format,
    mock_research,
    mock_scripts,
    mock_seo,
    _mock_visuals,
    mock_voice,
    _mock_long_video,
    _mock_short_video,
    _mock_social,
    mock_upload,
    _mock_analytics,
    _mock_persist,
    _mock_weekly,
    _mock_learning,
    tmp_path: Path,
):
    settings = MagicMock()
    settings.outputs_dir = tmp_path / "outputs"
    settings.database_url = "sqlite:///:memory:"
    settings.base_dir = tmp_path
    settings.ensure_dirs = MagicMock()
    mock_settings.return_value = settings

    first_story = _make_story("GitHub trending repo", 84.0, "github_trending")
    second_story = _make_story("OpenAI launches new agent", 88.0, "openai")
    mock_discover.return_value = [first_story, second_story]

    mock_verify.side_effect = [
        FactCheckResult(False, [], "Insufficient sources (2/3)", 0.4),
        FactCheckResult(
            True,
            [
                {"name": "OpenAI", "url": "https://openai.com", "verified": True},
                {"name": "TechCrunch", "url": "https://techcrunch.com", "verified": True},
                {"name": "Reuters", "url": "https://reuters.com", "verified": True},
            ],
            "LLM fact-check passed",
            0.9,
        ),
    ]

    mock_decide_format.return_value = ContentFormat.BOTH
    mock_research.return_value = MagicMock(summary_points=["OpenAI agent launch"])
    mock_scripts.return_value = MagicMock(
        script_long="word " * 500,
        script_short="short script",
        outline={"hook": "test"},
        script_sections=[{"label": "Hook", "text": "Hook text"}],
        script_short_sections=[{"label": "Hook", "text": "Short hook"}],
    )
    mock_seo.return_value = MagicMock(
        long_form={"title": "OpenAI Agent Launch", "intro": "Intro", "key_points": [], "tags": [], "hashtags": []},
        shorts={"title": "OpenAI Agent #Shorts", "hook": "Hook", "key_points": [], "tags": [], "hashtags": []},
        social={"x": "post"},
        keywords={},
    )
    mock_voice.return_value = (tmp_path / "voice.mp3", 120.0)
    mock_upload.side_effect = ["long123", "short456"]

    result = run_daily_pipeline(upload=True)

    assert result.success is True
    assert result.story_title == second_story.title
    assert mock_verify.call_count == 2
    assert mock_verify.call_args_list[1].kwargs["story_source"] == "openai"
