"""Master pipeline orchestrator — end-to-end daily run."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from futuredecoded.analytics.analytics_engine import generate_weekly_report, store_analytics_snapshot
from futuredecoded.analytics.learning_engine import analyse_and_update_preferences
from futuredecoded.config.channel_profile import ContentFormat
from futuredecoded.config.settings import get_settings
from futuredecoded.database.models import StoryRecord, StorySourceRecord, get_session, init_database
from futuredecoded.discovery.trend_engine import discover_and_score
from futuredecoded.editorial.content_strategist import decide_format
from futuredecoded.editorial.fact_checker import verify_story
from futuredecoded.editorial.script_generator import generate_scripts
from futuredecoded.media.thumbnail_engine import generate_thumbnail
from futuredecoded.media.video_engine import build_long_video, build_short_video
from futuredecoded.media.visual_collector import collect_visuals
from futuredecoded.media.voice_engine import synthesise_voice
from futuredecoded.publish.social_publisher import publish_social_posts
from futuredecoded.publish.youtube_uploader import upload_video
from futuredecoded.seo.seo_engine import enrich_seo

logger = logging.getLogger("futuredecoded.pipeline")


@dataclass
class PipelineResult:
    success: bool
    story_title: str
    output_dir: Path
    long_video_id: str | None = None
    short_video_id: str | None = None
    error: str = ""


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", slug).strip("-")[:60]


def run_daily_pipeline(upload: bool = True) -> PipelineResult:
    settings = get_settings()
    settings.ensure_dirs()
    init_database(settings.database_url)

    story = discover_and_score()
    if not story:
        return PipelineResult(False, "", settings.outputs_dir, error="No qualifying story found")

    topic_slug = _slugify(story.title)
    output_dir = settings.outputs_dir / topic_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Selected story (score=%.1f): %s", story.trend_score, story.title[:60])

    fact_result = verify_story(story.title, story.url, output_dir)
    if not fact_result.passed:
        return PipelineResult(False, story.title, output_dir, error=f"Fact check failed: {fact_result.reason}")

    content_format = decide_format(story)
    scripts = generate_scripts(story.title, story.url, output_dir)

    sources = [source.get("url", story.url) for source in fact_result.sources]
    seo = enrich_seo(story.title, scripts.script_long, scripts.script_short, sources, output_dir)

    keywords = [story.title.split()[0], "AI news", "tech news"]
    visuals = collect_visuals(topic_slug, keywords)

    long_video_id = None
    short_video_id = None

    if content_format in (ContentFormat.LONG, ContentFormat.BOTH):
        voice_long, _ = synthesise_voice(scripts.script_long, output_dir / "voice_long.mp3")
        srt_long = voice_long.with_suffix(".srt")
        video_long = build_long_video(
            scripts.script_long, voice_long, visuals,
            output_dir / "video_long.mp4", srt_long,
        )
        thumb_long = generate_thumbnail(
            video_long or output_dir / "video_long.mp4",
            seo.long_form.get("title", story.title)[:20],
            output_dir / "thumbnail_long.png",
        )
        if upload and video_long:
            long_video_id = upload_video(
                video_path=video_long,
                title=seo.long_form.get("title", story.title),
                description=seo.long_form.get("description", ""),
                tags=seo.long_form.get("tags", []),
                thumbnail_path=thumb_long,
                format_type="long",
                script=scripts.script_long,
            )
            if long_video_id:
                store_analytics_snapshot(long_video_id, {"views": 0, "ctr": 0.0, "retention": 0.0})

    if content_format in (ContentFormat.SHORT, ContentFormat.BOTH):
        voice_short, _ = synthesise_voice(scripts.script_short, output_dir / "voice_short.mp3")
        srt_short = voice_short.with_suffix(".srt")
        video_short = build_short_video(
            scripts.script_short, voice_short, visuals,
            output_dir / "video_short.mp4", srt_short,
        )
        thumb_short = generate_thumbnail(
            video_short or output_dir / "video_short.mp4",
            seo.shorts.get("title", story.title)[:15],
            output_dir / "thumbnail_short.png",
        )
        if upload and video_short:
            short_video_id = upload_video(
                video_path=video_short,
                title=seo.shorts.get("title", f"{story.title[:50]} #Shorts"),
                description=seo.shorts.get("description", ""),
                tags=seo.shorts.get("tags", []),
                thumbnail_path=thumb_short,
                format_type="short",
                script=scripts.script_short,
            )

    video_url = f"https://youtu.be/{long_video_id or short_video_id or 'pending'}"
    publish_social_posts(seo.social, video_url, output_dir)

    _persist_story(story, output_dir)
    generate_weekly_report(settings.base_dir / "outputs" / "weekly_report.html")
    analyse_and_update_preferences(settings.base_dir / "outputs" / "learning_insights.json")

    return PipelineResult(
        success=True,
        story_title=story.title,
        output_dir=output_dir,
        long_video_id=long_video_id,
        short_video_id=short_video_id,
    )


def _persist_story(story, output_dir: Path) -> None:
    session = get_session()
    try:
        record = StoryRecord(
            title=story.title,
            url=story.url,
            source=story.source,
            trend_score=story.trend_score,
            viral_probability=story.viral_probability,
            content_hash=story.content_hash,
            fact_checked=True,
        )
        session.add(record)
        session.commit()
    finally:
        session.close()
