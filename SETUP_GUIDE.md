# FutureDecoded V4 — Setup Guide

## 1. Prerequisites

- Python 3.12+
- ffmpeg + ffprobe
- edge-tts (`pip install edge-tts`)
- Google Cloud project with YouTube Data API v3 enabled

## 2. Install

```bash
git clone https://github.com/Mohan-Kumar-Swamynathan/futuredecoded-bot.git
cd futuredecoded-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install edge-tts
cp .env.example .env
```

## 3. Configure API Keys

Edit `.env`:

```env
GEMINI_API_KEY=your_key
GROQ_API_KEY=your_key
PEXELS_API_KEY=your_key
TREND_SCORE_THRESHOLD=80
```

## 4. YouTube OAuth (Separate from am/aalaya_mani bots)

1. Create OAuth credentials in Google Cloud Console (Desktop app)
2. Save as `config/futuredecoded_client_secrets.json`
3. Run auth:

```bash
PYTHONPATH=src python -m futuredecoded.main --auth-youtube
```

4. Token saved to `config/futuredecoded_youtube_token.pickle`

## 5. GitHub Actions Secrets

Encode credentials for CI:

```bash
base64 -i config/futuredecoded_youtube_token.pickle | pbcopy
# Paste as YOUTUBE_TOKEN_BASE64 secret

base64 -i config/futuredecoded_client_secrets.json | pbcopy
# Paste as CLIENT_SECRETS_BASE64 secret
```

Add all API keys as GitHub repo secrets.

## 6. Run Locally

```bash
# Dry run (generates everything, skips upload)
PYTHONPATH=src python -m futuredecoded.main --daily --dry-run

# Full production run
PYTHONPATH=src python -m futuredecoded.main --daily --upload
```

## 7. Docker

```bash
docker-compose up --build
```

## 8. Output Artifacts

Each story creates:

```
outputs/{topic-slug}/
├── outline.json
├── script_short.txt / script_long.txt
├── seo.json
├── voice_short.mp3 / voice_long.mp3
├── video_short.mp4 / video_long.mp4
├── thumbnail_short.png / thumbnail_long.png
└── fact_check_log.json
```

## 9. Troubleshooting

| Issue | Fix |
|-------|-----|
| No stories found | Lower `TREND_SCORE_THRESHOLD` in `.env` |
| edge-tts not found | `pip install edge-tts` |
| ffmpeg not found | `brew install ffmpeg` (macOS) |
| YouTube auth fails | Re-run `--auth-youtube`, check client secrets path |
| LLM errors | Ensure at least `GEMINI_API_KEY` or `GROQ_API_KEY` is set |
