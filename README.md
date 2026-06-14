# FutureDecoded V4 — AI & Tech News YouTube Automation

**Making Sense of Tomorrow**

Fully automated pipeline that discovers trending AI/tech stories, scores virality, fact-checks, generates **Shorts + long-form** videos with SEO-enriched metadata, and uploads to YouTube.

> **Separate from `am` / `aalaya_mani` bots** — uses its own credentials, database, and YouTube channel config.

## Features

- 17-phase pipeline: discovery → scoring → fact-check → scripts → voice → visuals → video → SEO → upload → social → analytics
- Dual format: 1080×1920 Shorts (45–60s) + 1920×1080 long-form (5–10 min)
- SEO enrichment: scored titles, keyword descriptions, chapters, source citations
- SQLite persistence with upload deduplication
- LLM fallback: Gemini → Groq → OpenRouter → OpenAI → Ollama
- GitHub Actions daily run at **08:00 IST**

## Quick Start

```bash
cd futuredecoded-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install edge-tts
cp .env.example .env
# Edit .env with your API keys

# Dry run (no upload)
PYTHONPATH=src python -m futuredecoded.main --daily --dry-run

# YouTube OAuth (once)
PYTHONPATH=src python -m futuredecoded.main --auth-youtube

# Full run with upload
PYTHONPATH=src python -m futuredecoded.main --daily --upload
```

## Project Structure

```
futuredecoded-bot/
├── src/futuredecoded/       # All Python modules
├── config/                  # channel.yaml + YouTube OAuth (separate from am bots)
├── database/                # SQLite DB
├── outputs/                 # Per-topic artifacts
├── assets/                  # BGM, visuals
├── tests/
├── .github/workflows/       # Daily CI at 08:00 IST
├── Dockerfile
└── docker-compose.yml
```

## GitHub Actions

Add these secrets to your repo:

| Secret | Required |
|--------|----------|
| `GEMINI_API_KEY` | Yes |
| `GROQ_API_KEY` | Recommended |
| `PEXELS_API_KEY` | Recommended |
| `YOUTUBE_TOKEN_BASE64` | For upload |
| `CLIENT_SECRETS_BASE64` | For upload |

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for full setup.

## License

MIT
