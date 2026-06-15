"""FutureDecoded channel brand — separate YouTube channel from am/aalaya_mani."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


CHANNEL_NAME = "FutureDecoded"
CHANNEL_TAGLINE = "Making Sense of Tomorrow"
YOUTUBE_CATEGORY_ID = "28"
DEFAULT_LANGUAGE = "en"

TOPIC_KEYWORDS = [
    "artificial intelligence",
    "OpenAI",
    "ChatGPT",
    "Google AI",
    "Anthropic",
    "robotics",
    "startup",
    "space technology",
    "developer tools",
    "AI agents",
    "tech news",
]

RSS_FEEDS = {
    "google_ai": "https://blog.google/technology/ai/rss/",
    "openai": "https://openai.com/blog/rss.xml",
    "anthropic": "https://www.anthropic.com/news/rss",
    "deepmind": "https://deepmind.google/blog/rss.xml",
    "microsoft_ai": "https://blogs.microsoft.com/ai/feed/",
    "nvidia_ai": "https://blogs.nvidia.com/feed/",
    "meta_ai": "https://ai.meta.com/blog/rss/",
    "techcrunch": "https://techcrunch.com/feed/",
    "the_verge": "https://www.theverge.com/rss/index.xml",
    "ars_technica": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "wired": "https://www.wired.com/feed/rss",
    "amazon_news": "https://www.aboutamazon.com/news/feed",
    "tesla_news": "https://www.tesla.com/blog/rss",
}

REDDIT_SUBREDDITS = ["OpenAI", "artificial", "singularity", "MachineLearning"]

HN_API = "https://hacker-news.firebaseio.com/v0"


class ContentFormat(str, Enum):
    SHORT = "short"
    LONG = "long"
    BOTH = "both"


class StoryCategory(str, Enum):
    BREAKING_NEWS = "BREAKING_NEWS"
    MAJOR_LAUNCH = "MAJOR_LAUNCH"
    EDUCATIONAL = "EDUCATIONAL"
    DEV_TOOL = "DEV_TOOL"
    STARTUP = "STARTUP"


@dataclass(frozen=True)
class VideoSpec:
    width: int
    height: int
    min_duration_s: int
    max_duration_s: int


LONG_FORM_SPEC = VideoSpec(1920, 1080, 240, 360)
SHORTS_SPEC = VideoSpec(1080, 1920, 30, 60)

EDGE_TTS_VOICE = "en-US-GuyNeural"
EDGE_TTS_RATE = "-5%"
EDGE_TTS_PITCH = "+0Hz"

GEMINI_TTS_MODELS = (
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-preview-tts",
    "gemini-3.1-flash-tts-preview",
)
GEMINI_TTS_VOICE = "Charon"
GEMINI_TTS_MAX_CHARS_PER_CHUNK = 1500

BGM_FILENAME_LONG = "long_form.mp3"
BGM_FILENAME_SHORT = "shorts.mp3"
BGM_MUSIC_VOLUME_LONG = 0.12
BGM_MUSIC_VOLUME_SHORT = 0.10

WATERMARK_FILENAME = "watermark.png"
WATERMARK_OPACITY = 0.78
WATERMARK_MARGIN_PX = 24

VIDEO_EXPORT_FPS = 30
VIDEO_MAX_SCENE_SECONDS = 5.0
VIDEO_MIN_SCENE_SECONDS = 3.0

MAX_IMAGES_LONG = 12
MAX_IMAGES_SHORT = 6
TITLE_VARIANT_COUNT = 10
THUMBNAIL_VARIANT_COUNT = 10
MIN_FACT_SOURCES = 3
