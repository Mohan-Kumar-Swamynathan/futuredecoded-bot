"""Master pipeline orchestrator — end-to-end daily run."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

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
from futuredecoded.media.visual_collector import collect_visuals_for_story
from futuredecoded.media.voice_engine import synthesise_voice
from futuredecoded.publish.schedule_planner import (
    resolve_long_form_publish_time_utc,
    resolve_shorts_publish_time_utc,
)
from futuredecoded.publish.social_publisher import publish_social_posts
from futuredecoded.publish.youtube_uploader import upload_video
from futuredecoded.seo.chapter_builder import build_chapters_from_sections
from futuredecoded.seo.description_formatter import build_long_form_description, build_shorts_description
from futuredecoded.seo.seo_engine import enrich_seo

logger = logging.getLogger("futuredecoded.pipeline")
IST = ZoneInfo("Asia/Kolkata")


@dataclass
class PipelineResult:
    success: bool
    story_title: str
    output_dir: Path
    long_video_id: str | None = None
    short_video_id: str | None = None
    error: str = ""


def _order_images_for_sections(
    images: list[Path],
    sections: list[dict[str, str]],
) -> list[Path]:
    if not images or not sections:
        return images
    ordered: list[Path] = []
    for index in range(len(sections)):
        ordered.append(images[index % len(images)])
    for image in images:
        if image not in ordered:
            ordered.append(image)
    return ordered


def _save_description(output_dir: Path, filename: str, description: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / filename).write_text(description, encoding="utf-8")


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

    visuals_long = collect_visuals_for_story(
        topic_slug=topic_slug,
        story_title=story.title,
        outline=scripts.outline,
        sections=scripts.script_sections,
        max_images=8,
        orientation="landscape",
    )
    visuals_short = collect_visuals_for_story(
        topic_slug=topic_slug,
        story_title=story.title,
        outline=scripts.outline,
        sections=scripts.script_short_sections,
        max_images=4,
        orientation="portrait",
    )
    visuals_long = _order_images_for_sections(visuals_long, scripts.script_sections)
    visuals_short = _order_images_for_sections(visuals_short, scripts.script_short_sections)
    hero_image = visuals_long[0] if visuals_long else None

    long_publish_at = resolve_long_form_publish_time_utc()
    short_publish_at = resolve_shorts_publish_time_utc()
    logger.info(
        "Long-form YouTube publish scheduled for %s",
        long_publish_at.astimezone(IST).strftime("%I:%M %p IST").lstrip("0"),
    )
    logger.info(
        "Shorts YouTube publish scheduled for %s",
        short_publish_at.astimezone(IST).strftime("%I:%M %p IST").lstrip("0"),
    )

    long_video_id = None
    short_video_id = None

    if content_format in (ContentFormat.LONG, ContentFormat.BOTH):
        voice_long, duration_long = synthesise_voice(scripts.script_long, output_dir / "voice_long.mp3")
        chapters_long = build_chapters_from_sections(
            scripts.script_sections,
            duration_long,
            fallback_script=scripts.script_long,
            format_type="long",
        )
        long_description = build_long_form_description(
            intro=seo.long_form.get("intro", story.title),
            key_points=seo.long_form.get("key_points", []),
            chapters=chapters_long,
            sources=sources,
            hashtags=seo.long_form.get("hashtags"),
        )
        _save_description(output_dir, "description_long.txt", long_description)
        srt_long = voice_long.with_suffix(".srt")
        video_long = build_long_video(
            scripts.script_long, voice_long, visuals_long,
            output_dir / "video_long.mp4", srt_long,
        )
        thumb_long = generate_thumbnail(
            video_long or output_dir / "video_long.mp4",
            seo.long_form.get("title", story.title)[:20],
            output_dir / "thumbnail_long.png",
            hero_image=hero_image,
        )
        if upload and video_long:
            long_video_id = upload_video(
                video_path=video_long,
                title=seo.long_form.get("title", story.title),
                description=long_description,
                tags=seo.long_form.get("tags", []),
                thumbnail_path=thumb_long,
                format_type="long",
                script=scripts.script_long,
                publish_at_utc=long_publish_at,
            )
            if long_video_id:
                store_analytics_snapshot(long_video_id, {"views": 0, "ctr": 0.0, "retention": 0.0})

    if content_format in (ContentFormat.SHORT, ContentFormat.BOTH):
        voice_short, duration_short = synthesise_voice(scripts.script_short, output_dir / "voice_short.mp3")
        chapters_short = build_chapters_from_sections(
            scripts.script_short_sections,
            duration_short,
            fallback_script=scripts.script_short,
            format_type="short",
        )
        shorts_description = build_shorts_description(
            hook=seo.shorts.get("hook", story.title),
            key_points=seo.shorts.get("key_points", []),
            sources=sources,
            hashtags=seo.shorts.get("hashtags"),
            chapters=chapters_short,
        )
        _save_description(output_dir, "description_short.txt", shorts_description)
        srt_short = voice_short.with_suffix(".srt")
        video_short = build_short_video(
            scripts.script_short, voice_short, visuals_short,
            output_dir / "video_short.mp4", srt_short,
        )
        thumb_short = generate_thumbnail(
            video_short or output_dir / "video_short.mp4",
            seo.shorts.get("title", story.title)[:15],
            output_dir / "thumbnail_short.png",
            hero_image=visuals_short[0] if visuals_short else hero_image,
        )
        if upload and video_short:
            short_video_id = upload_video(
                video_path=video_short,
                title=seo.shorts.get("title", f"{story.title[:50]} #Shorts"),
                description=shorts_description,
                tags=seo.shorts.get("tags", []),
                thumbnail_path=thumb_short,
                format_type="short",
                script=scripts.script_short,
                publish_at_utc=short_publish_at,
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
