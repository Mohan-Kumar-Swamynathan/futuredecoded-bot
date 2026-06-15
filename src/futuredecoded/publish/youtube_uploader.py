"""YouTube uploader — separate credentials from am/aalaya_mani bots."""

from __future__ import annotations

import base64
import hashlib
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional

from futuredecoded.config.channel_profile import DEFAULT_LANGUAGE, UPLOAD_CUSTOM_THUMBNAILS, YOUTUBE_CATEGORY_ID
from futuredecoded.config.settings import get_settings
from futuredecoded.database.models import UploadHistoryRecord, get_session
from futuredecoded.publish.schedule_planner import format_publish_at_for_youtube

logger = logging.getLogger("futuredecoded.publish.youtube")

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
]


def content_hash(title: str, script_prefix: str) -> str:
    return hashlib.sha256(f"{title}:{script_prefix[:500]}".encode()).hexdigest()


def is_duplicate(title: str, script: str) -> bool:
    content_hash_value = content_hash(title, script)
    session = get_session()
    try:
        existing = session.query(UploadHistoryRecord).filter_by(
            content_hash=content_hash_value
        ).first()
        return existing is not None
    finally:
        session.close()


def record_upload(title: str, script: str, video_id: str, format_type: str) -> None:
    session = get_session()
    try:
        record = UploadHistoryRecord(
            video_id=video_id,
            format_type=format_type,
            title=title,
            content_hash=content_hash(title, script),
            uploaded_at=datetime.utcnow(),
        )
        session.add(record)
        session.commit()
    finally:
        session.close()


def _restore_token_from_env() -> object | None:
    settings = get_settings()
    if settings.youtube_token_base64:
        try:
            return pickle.loads(base64.b64decode(settings.youtube_token_base64))
        except Exception as exc:
            logger.warning("Could not decode YOUTUBE_TOKEN_BASE64: %s", exc)
    if settings.client_secrets_base64:
        secrets_path = settings.youtube_client_secrets
        secrets_path.parent.mkdir(parents=True, exist_ok=True)
        secrets_path.write_bytes(base64.b64decode(settings.client_secrets_base64))
    return None


def get_authenticated_service():
    try:
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        logger.error("Google API packages not installed")
        return None

    settings = get_settings()
    creds = _restore_token_from_env()
    token_file = settings.base_dir / settings.youtube_token_file

    if not creds and token_file.exists():
        with open(token_file, "rb") as file:
            creds = pickle.load(file)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secrets_path = settings.base_dir / settings.youtube_client_secrets
            if not secrets_path.exists():
                logger.error("YouTube client secrets not found: %s", secrets_path)
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=8090)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_file, "wb") as file:
            pickle.dump(creds, file)

    return build("youtube", "v3", credentials=creds)


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    thumbnail_path: Path | None = None,
    privacy: str = "private",
    format_type: str = "long",
    script: str = "",
    publish_at_utc: datetime | None = None,
) -> str | None:
    settings = get_settings()
    if settings.dry_run:
        publish_label = format_publish_at_for_youtube(publish_at_utc) if publish_at_utc else "immediate"
        logger.info("[DRY RUN] Would upload: %s (publish=%s)", title, publish_label)
        return "DRY_RUN_VIDEO_ID"

    if is_duplicate(title, script):
        logger.warning("Duplicate upload skipped: %s", title[:50])
        return None

    youtube = get_authenticated_service()
    if not youtube:
        return None

    from googleapiclient.http import MediaFileUpload

    status_body: dict = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": False,
    }
    if publish_at_utc is not None:
        status_body["publishAt"] = format_publish_at_for_youtube(publish_at_utc)
        status_body["privacyStatus"] = "private"

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": YOUTUBE_CATEGORY_ID,
            "defaultLanguage": DEFAULT_LANGUAGE,
        },
        "status": status_body,
    }

    media = MediaFileUpload(str(video_path), chunksize=1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info("Upload progress: %d%%", int(status.progress() * 100))

    video_id = response["id"]
    if publish_at_utc is not None:
        logger.info(
            "Uploaded and scheduled: https://youtu.be/%s at %s",
            video_id,
            format_publish_at_for_youtube(publish_at_utc),
        )
    else:
        logger.info("Uploaded: https://youtu.be/%s", video_id)

    if UPLOAD_CUSTOM_THUMBNAILS and thumbnail_path and thumbnail_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path)),
            ).execute()
            logger.info("Thumbnail uploaded for video %s", video_id)
        except Exception as exc:
            logger.warning("Thumbnail upload failed (video already uploaded): %s", exc)
    elif thumbnail_path and thumbnail_path.exists():
        logger.info(
            "Custom thumbnail upload skipped — using YouTube auto thumbnail for https://youtu.be/%s",
            video_id,
        )

    record_upload(title, script, video_id, format_type)
    return video_id
