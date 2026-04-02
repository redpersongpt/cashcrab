<p align="center">
  <img src="assets/cashcrab.png" width="280" alt="CashCrab mascot" />
</p>

<h1 align="center">CashCrab</h1>

<p align="center">
  <strong>Your claws on autopilot.</strong><br>
  YouTube Shorts, Twitter affiliate posts, and local lead gen — all from one CLI.<br>
  No API keys for AI. Uses your existing subscriptions.
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> &bull;
  <a href="#features">Features</a> &bull;
  <a href="#vs-moneyprinterv2">vs MoneyPrinterV2</a> &bull;
  <a href="#commands">Commands</a> &bull;
  <a href="#architecture">Architecture</a>
</p>

---

## Why CashCrab?

Most "money printer" tools either **break every week** (Selenium on YouTube DOM lol) or **cost more to run than they earn** (pay-per-token APIs eating your margins).

CashCrab fixes both:

- **Zero AI cost** — routes through your ChatGPT/Claude/Gemini subscriptions via `g4f`. No API keys.
- **Official APIs only** — YouTube Data API v3, Twitter OAuth 2.0. No Selenium. No DOM scraping. No Firefox profiles.
- **Free TTS** — 300+ natural voices via `edge-tts`. Not some pinned wheel from 2023.
- **Actually works** — no recursive stack overflows, no broken schedulers, no zombie browser processes.

## vs MoneyPrinterV2

| | MoneyPrinterV2 | CashCrab |
|---|---|---|
| YouTube upload | Selenium (breaks on UI update) | Official YouTube API v3 |
| Twitter posting | Selenium + Firefox profile | Twitter OAuth 2.0 PKCE |
| AI text gen | Ollama only (local) | g4f: GPT-4o, Claude, Gemini — your subs |
| AI images | Gemini API only | g4f DALL-E + Pexels stock video |
| TTS | KittenTTS (8 voices, pinned) | edge-tts (300+ voices, free) |
| Subtitles | "Planned" (unchecked roadmap) | Built-in from word-level TTS timing |
| Scheduler | Broken — jobs never fire | APScheduler + SQLite persistence |
| Error handling | Recursive retry → stack overflow | Exponential backoff, max 3 retries |
| Email outreach | Sends to noreply@ addresses | Filters junk, CAN-SPAM compliant |
| Config | Re-reads JSON on every function call | Loaded once, cached |
| Auth | Manual token copy-paste | OAuth browser flow, auto-refresh |
| FTC compliance | None | Auto-adds #ad to affiliate tweets |
| Dependencies | Downloads & compiles Go binary at runtime | pip install, done |

## Quickstart

```bash
git clone https://github.com/YOUR_USER/cashcrab.git
cd cashcrab
pip install -r requirements.txt
cp config.example.json config.json
```

Link your accounts:
```bash
python main.py auth youtube    # opens browser → authorize → done
python main.py auth twitter    # opens browser → authorize → done
python main.py auth keys       # set Pexels + Google Places keys
```

Generate your first Short:
```bash
python main.py yt generate --topic "5 habits of millionaires"
```

## Features

### YouTube Shorts Factory
LLM writes the script → edge-tts narrates with word-level subtitles → Pexels stock footage or AI images → moviepy assembles 1080x1920 vertical video → uploads via official API.

```bash
python main.py yt generate                     # full auto
python main.py yt generate --topic "AI tools"  # pick a topic
python main.py yt generate --no-upload         # generate only
python main.py yt upload-all                   # upload pending
python main.py yt status                       # see queue
```

### Twitter Affiliate Bot
Mixes organic value tweets with affiliate promotions. Auto-adds `#ad` for FTC compliance. OAuth 2.0 with PKCE — no manual token juggling.

```bash
python main.py tw post --count 5                  # mix of organic + affiliate
python main.py tw affiliate                        # single affiliate tweet
python main.py tw organic --topic "productivity"   # value tweet
python main.py tw raw "My custom tweet"            # post anything
```

### Local Lead Finder + Cold Outreach
Google Places API finds businesses → scrapes websites for emails → filters out junk addresses → sends CAN-SPAM compliant outreach.

```bash
python main.py leads find --query "dentist" --location "Miami, FL"
python main.py leads outreach --csv leads.csv --dry-run   # preview
python main.py leads outreach --csv leads.csv --send       # send
```

### Full Autopilot
```bash
python main.py auto --shorts 2 --tweets 5 --find-leads
python main.py schedule   # runs forever on cron
```

## Commands

```
main.py
├── auth
│   ├── youtube     # OAuth2 browser login
│   ├── twitter     # OAuth2 PKCE browser login
│   ├── keys        # set Pexels / Google Places API keys
│   ├── status      # show all auth status
│   └── revoke      # remove tokens
├── yt
│   ├── generate    # create + upload a Short
│   ├── upload-all  # upload pending from shorts/
│   └── status      # queue status
├── tw
│   ├── post        # batch tweets (organic + affiliate mix)
│   ├── affiliate   # single affiliate tweet
│   ├── organic     # single value tweet
│   └── raw         # post exact text
├── leads
│   ├── find        # discover businesses
│   └── outreach    # send emails
├── schedule        # run YouTube + Twitter on cron
└── auto            # one-shot: shorts + tweets + leads
```

## Architecture

```
cashcrab/
├── main.py                 # Click CLI
├── config.example.json     # Template (no secrets)
├── modules/
│   ├── auth.py             # OAuth2 flows + API key storage
│   ├── config.py           # Load-once config
│   ├── llm.py              # g4f (free) / Ollama (local)
│   ├── tts.py              # edge-tts (free, 300+ voices)
│   ├── video.py            # Script → audio → visuals → MP4
│   ├── youtube.py          # YouTube Data API v3
│   ├── twitter.py          # Twitter API v2 via tweepy
│   ├── leads.py            # Google Places + email scraper
│   └── scheduler.py        # APScheduler + SQLite jobs
├── tokens/                 # OAuth tokens (gitignored)
├── shorts/                 # Generated videos
└── assets/
    └── cashcrab.png        # Pixel art mascot
```

## Cost Breakdown

| Component | Cost |
|-----------|------|
| AI text generation (scripts, tweets, metadata) | $0 (g4f / your subscriptions) |
| AI image generation | $0 (g4f) |
| Text-to-speech | $0 (edge-tts) |
| Stock video footage | $0 (Pexels free tier) |
| YouTube upload | $0 (official API) |
| Twitter posting | $0 (free tier API) |
| **Total per video** | **$0** |

## Configuration

Copy `config.example.json` to `config.json`. Key sections:

```json
{
  "llm": {
    "provider": "g4f",
    "model": "gpt-4o-mini"
  },
  "tts": {
    "provider": "edge",
    "voice": "en-US-ChristopherNeural"
  },
  "youtube": {
    "niche": "productivity tips",
    "schedule_hours": [9, 15]
  }
}
```

Full config reference in [`config.example.json`](config.example.json).

## Requirements

- Python 3.10+
- Google Cloud project with YouTube Data API v3 enabled (for `client_secrets.json`)
- Twitter Developer account with OAuth 2.0 enabled
- Optional: Pexels API key (free), Google Places API key

## Contributing

PRs welcome. Keep it modular — each feature is its own file in `modules/`.

## License

MIT
