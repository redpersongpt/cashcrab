# Contributing to CashCrab

Thanks for wanting to help the crab grow its treasure chest.

## Getting Started

```bash
git clone https://github.com/YOUR_USER/cashcrab.git
cd cashcrab
python3 -m venv venv && source venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
cp config.example.json config.json
```

## Project Structure

Each feature is a single file in `modules/`. Keep it that way.

```
modules/
├── auth.py        # OAuth2 flows + API key storage
├── config.py      # Load-once config
├── llm.py         # AI text generation (g4f / Ollama)
├── tts.py         # Text-to-speech (edge-tts)
├── video.py       # Video generation pipeline
├── youtube.py     # YouTube upload via official API
├── twitter.py     # Twitter posting via official API
├── leads.py       # Lead finder + email outreach
└── scheduler.py   # APScheduler cron jobs
```

## Rules

1. **No Selenium.** We use official APIs. If a platform doesn't have one, we don't automate it.
2. **No API keys for AI.** g4f or Ollama. Users shouldn't pay to run this.
3. **No hardcoded secrets.** Everything goes through `config.json` or `tokens/`.
4. **One module = one feature.** Don't cross-wire modules. They talk through `main.py`.
5. **Error handling.** Retry with backoff, max 3 attempts, then fail with a clear message. No recursive retries.
6. **Menu-first UX.** The default `cashcrab` experience must stay simple, colorful, and understandable without memorizing commands.

## Adding a New Platform

1. Create `modules/newplatform.py`
2. Add OAuth flow to `modules/auth.py` if needed
3. Add config section to `config.example.json`
4. Add CLI commands to `main.py`
5. Update README

## Pull Requests

- One feature per PR
- Test your changes locally before submitting
- Update README if you add commands
- Keep commits atomic

## Bug Reports

Include:
- Python version
- OS
- Full error traceback
- Steps to reproduce

## Ideas We'd Love

- TikTok upload via official API
- Instagram Reels support
- Analytics dashboard (track views/engagement)
- Webhook notifications (Discord/Slack)
- Multi-language content generation
- A/B testing for tweet copy
