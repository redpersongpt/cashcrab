<p align="center">
  <img src="assets/cashcrab.png" width="280" alt="CashCrab mascot" />
</p>

<h1 align="center">CashCrab</h1>

<p align="center">
  <strong>Your claws on autopilot.</strong><br>
  YouTube Shorts, Twitter affiliate posts, and local lead gen from one terminal app.
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

Most money-tool repos are the same mess:

- Selenium glued to random websites until one UI change kills it
- ten setup steps before you can test one thing
- docs written like a generic AI landing page

CashCrab is supposed to be simpler:

- **run one install command**
- **get a real `cashcrab` command in your terminal**
- **open a menu instead of memorizing flags**
- **use official APIs where possible**

## vs MoneyPrinterV2

| | MoneyPrinterV2 | CashCrab |
|---|---|---|
| YouTube upload | Selenium | Official YouTube API v3 |
| Twitter posting | Selenium + browser profile hacks | Twitter / X OAuth 2.0 PKCE |
| AI text gen | Ollama only | `g4f` with GPT / Claude / Gemini routes |
| TTS | Narrow voice set | `edge-tts` |
| Scheduler | Fragile | APScheduler + SQLite persistence |
| Auth flow | Manual and annoying | Browser login + saved tokens |
| CLI UX | Raw commands only | Menu-first terminal app + commands |
| Install story | Repo-local | Global `cashcrab` install scripts |

## Quickstart

macOS / Linux / WSL:

```bash
curl -fsSL https://raw.githubusercontent.com/redpersongpt/cashcrab/main/scripts/install.sh | bash
cashcrab
```

PowerShell:

```powershell
irm https://raw.githubusercontent.com/redpersongpt/cashcrab/main/scripts/install.ps1 | iex
cashcrab
```

That install flow does the boring setup work for you:

- checks for Python
- tries to install missing basics where possible
- creates a private user-level venv
- installs CashCrab
- adds a global `cashcrab` launcher
- warns you if optional media tools like `ffmpeg` are missing

If `cashcrab` is not found right away, restart the terminal and run it again.

## First Run

Inside the app:

1. Open `Setup accounts and API keys`
2. Connect YouTube
3. Connect Twitter / X
4. Save your Pexels and Google Places keys
5. Go back and pick what you want to run

## Features

### Menu-first terminal app

Run `cashcrab` and it opens a colorful terminal UI with numbered menus, panels, clear prompts, and status screens.

### YouTube Shorts factory

Generate a topic, script, voiceover, subtitles, visuals, and final vertical video, then upload it through the official API.

```bash
cashcrab yt generate
cashcrab yt generate --topic "5 habits of millionaires"
cashcrab yt generate --no-upload
cashcrab yt upload-all
cashcrab yt status
```

### Twitter / X affiliate bot

Post useful tweets, affiliate tweets, or mixed batches. Affiliate posts automatically include `#ad`.

```bash
cashcrab tw post --count 5 --affiliate-ratio 0.3
cashcrab tw affiliate
cashcrab tw organic --topic "productivity"
cashcrab tw raw "My custom tweet"
```

### Lead finder and outreach

Find businesses with Google Places, scrape public emails, export CSVs, and preview or send outreach.

```bash
cashcrab leads find --query "dentist" --location "Miami, FL"
cashcrab leads outreach --csv leads.csv --dry-run
cashcrab leads outreach --csv leads.csv --send
```

### Full autopilot

```bash
cashcrab auto --shorts 2 --tweets 5 --find-leads
cashcrab schedule
```

## Commands

```text
cashcrab
├── auth
│   ├── youtube
│   ├── twitter
│   ├── keys
│   ├── status
│   └── revoke
├── yt
│   ├── generate
│   ├── upload-all
│   └── status
├── tw
│   ├── post
│   ├── affiliate
│   ├── organic
│   └── raw
├── leads
│   ├── find
│   └── outreach
├── dashboard
├── schedule
└── auto
```

## Architecture

```text
cashcrab/
├── main.py
├── pyproject.toml
├── config.example.json
├── scripts/
│   ├── install.sh
│   └── install.ps1
├── modules/
│   ├── auth.py
│   ├── analytics.py
│   ├── config.py
│   ├── leads.py
│   ├── notify.py
│   ├── scheduler.py
│   ├── tiktok.py
│   ├── tts.py
│   ├── twitter.py
│   ├── ui.py
│   ├── video.py
│   └── youtube.py
├── assets/
├── shorts/
└── tokens/
```

## What You Still Need

- `client_secrets.json` for YouTube
- Twitter / X OAuth credentials in `config.json`
- optional Pexels key
- optional Google Places key

The installer sets up the app. Your platform credentials are still yours to provide.

## License

MIT
