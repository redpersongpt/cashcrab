<p align="center">
  <img src="assets/cashcrab.png" width="280" alt="CashCrab mascot" />
</p>

<h1 align="center">CashCrab</h1>

<p align="center">
  <strong>A colorful terminal app for YouTube Shorts, X posting, and local lead generation.</strong><br>
  Beginner-first menu by default. Power-user commands still available.
</p>

## Quick Start

```bash
git clone https://github.com/YOUR_USER/cashcrab.git
cd cashcrab
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
cp config.example.json config.json
cashcrab
```

Inside the app:

1. Open `Setup accounts and API keys`
2. Connect YouTube and Twitter / X
3. Save your Pexels and Google Places keys
4. Go back and pick the workflow you want

If you do not want the installed command, this still works:

```bash
python3 main.py
```

## Why It Is Simpler Now

- Running `cashcrab` opens a numbered menu automatically.
- Every screen uses the same colorful terminal layout.
- `0` always goes back.
- Status, errors, and next steps use plain language.
- The old command mode still exists for automation and scripts.

## Most Useful Commands

The app is built for the interactive menu first, but these direct commands still work:

```bash
cashcrab yt generate --topic "5 habits of millionaires"
cashcrab yt upload-all
cashcrab tw post --count 3 --affiliate-ratio 0.3
cashcrab leads find --query "dentist" --location "Miami, FL"
cashcrab leads outreach --csv leads.csv --dry-run
cashcrab auto --shorts 1 --tweets 3 --find-leads
cashcrab schedule
```

## Features

### YouTube Shorts

- Generates a topic, script, voiceover, subtitles, visuals, and final video
- Uploads through the official YouTube API
- Keeps pending Shorts in `shorts/`

### Twitter / X

- Posts helpful or affiliate tweets
- Uses OAuth 2.0 PKCE
- Adds `#ad` to affiliate tweets automatically

### Local Lead Finder

- Finds businesses with Google Places
- Scrapes public websites for email addresses
- Exports leads to CSV
- Can preview or send outreach emails

### Automation

- One-shot autopilot mode
- APScheduler-based recurring jobs
- Simple terminal dashboard for status

## Install Notes

`cashcrab` is now exposed as a real console command through `pyproject.toml`, so local installs work with:

```bash
python3 -m pip install -e .
```

If you want a cleaner global install, `pipx install .` is the next step.

An exact `install cashcrab` flow would require publishing the package or wiring a system package manager. The repo is now structured for that path.

## Configuration

Copy `config.example.json` to `config.json`.

Main sections:

- `llm`: text generation provider and model
- `tts`: voice and speech rate
- `youtube`: upload defaults and scheduling
- `visuals`: `pexels` or `dalle`
- `twitter`: client credentials and affiliate products
- `leads`: search targets, SMTP, and outreach template

## Requirements

- Python 3.10+
- YouTube Data API v3 credentials in `client_secrets.json`
- Twitter / X developer app with OAuth 2.0 enabled
- Optional Pexels API key for stock footage
- Optional Google Places API key for lead generation

## Project Layout

```text
cashcrab/
├── main.py
├── pyproject.toml
├── config.example.json
├── modules/
│   ├── auth.py
│   ├── config.py
│   ├── leads.py
│   ├── scheduler.py
│   ├── tts.py
│   ├── twitter.py
│   ├── ui.py
│   ├── video.py
│   └── youtube.py
├── assets/
└── shorts/
```

## License

MIT
