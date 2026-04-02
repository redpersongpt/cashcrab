<p align="center">
  <img src="assets/cashcrab.png" width="280" alt="CashCrab mascot" />
</p>

<h1 align="center">CashCrab</h1>

<p align="center">
  <strong>X engagement autopilot.</strong><br>
  Voice-matched posting, smart engagement, thread generation, and autonomous growth from your terminal.
</p>

<p align="center">
  <a href="#how-it-works">How it works</a> &bull;
  <a href="#quickstart">Quickstart</a> &bull;
  <a href="#commands">Commands</a> &bull;
  <a href="#configuration">Configuration</a>
</p>

---

## How it works

One command. Your X account grows on autopilot.

```bash
cashcrab tw autopilot --keywords "AI,automation,tech" --duration 60
```

Every 60 minutes the scheduler runs a cycle:

| Step | What happens |
|---|---|
| **Voice AI** | Analyzes your past tweets, builds a style profile, generates posts indistinguishable from you |
| **Content scoring** | Every draft gets a 0-100 score. Weak drafts are rejected before posting |
| **Smart engage** | Searches tweets by keyword, scores them (account size, recency, reciprocal potential), auto-likes |
| **AI reply** | Generates contextual replies in your voice on high-scoring tweets |
| **Thread gen** | Writes multi-tweet threads: hook, value, value, CTA |
| **Anti-detection** | Random 30s-3min pauses, daily caps, human-like timing |

The brain is Qwen (free, no API cost). Also works with g4f, Ollama, or any OpenAI-compatible provider.

---

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

### First run

1. `cashcrab` opens the menu
2. Go to **Setup accounts and API keys**
3. Connect **Qwen OAuth** (recommended brain)
4. Connect **Twitter / X**
5. Go back, open **Twitter / X** > **X Engagement Autopilot**
6. Run **Analyze my voice** once
7. Start the autopilot

Or skip the menu:

```bash
cashcrab auth qwen
cashcrab auth twitter
cashcrab tw voice-analyze
cashcrab tw autopilot --duration 60
```

---

## Commands

### Engagement autopilot

```bash
# Analyze your writing voice (run once)
cashcrab tw voice-analyze --count 50

# Generate a tweet in your exact voice
cashcrab tw voice-post --topic "AI workflows" --post

# Score a draft before posting
cashcrab tw score "Your draft tweet text here"

# Search and engage (like + AI reply)
cashcrab tw engage --keywords "AI,startups" --max-likes 15 --max-replies 5

# Find accounts worth engaging with
cashcrab tw targets --keywords "AI,tech" --min-followers 500 --max-followers 50000

# Post a thread
cashcrab tw thread --topic "5 AI automation tips" --count 5 --post

# Full autopilot (runs for 60 min)
cashcrab tw autopilot --duration 60

# Engagement stats
cashcrab tw engage-stats
```

### Posting and queue

```bash
# Post tweets
cashcrab tw post --count 5 --affiliate-ratio 0.3
cashcrab tw organic --topic "productivity"
cashcrab tw affiliate
cashcrab tw raw "My custom tweet"

# Draft and queue
cashcrab tw draft --topic "AI tips"
cashcrab tw queue --preset authority --topic "AI" --count 4
cashcrab tw queue-list
cashcrab tw post-queued --limit 2
cashcrab tw export-queue
```

### Scheduler

```bash
# Run everything once
cashcrab auto --tweets 3 --engage --engage-duration 30

# Always-on autopilot (every 60 min)
cashcrab schedule
```

### Full command tree

```text
cashcrab
├── tw
│   ├── autopilot          # Thought leader agent loop
│   ├── voice-analyze      # Build your writing voice profile
│   ├── voice-post         # Post in your exact voice
│   ├── engage             # Search & auto-engage
│   ├── targets            # Find engagement targets
│   ├── thread             # Generate and post threads
│   ├── score              # Score a draft 0-100
│   ├── engage-stats       # Activity summary
│   ├── post               # Batch post
│   ├── affiliate           # Post affiliate tweet
│   ├── organic            # Post organic tweet
│   ├── raw                # Post exact text
│   ├── draft              # Draft + queue
│   ├── queue              # Workflow queue builder
│   ├── queue-list         # Show queue
│   ├── post-queued        # Drain queue
│   └── export-queue       # Export as Markdown
├── auth
│   ├── qwen               # Connect Qwen OAuth
│   ├── twitter             # Connect X account
│   ├── keys               # Save API keys
│   ├── status             # Auth status
│   └── revoke             # Remove saved login
├── skills                  # Browse skill packs
├── agents                  # Browse sub-agent roles
├── schedule               # Always-on scheduler
├── auto                   # Run once
├── dashboard              # Analytics
└── onboard                # AI setup wizard
```

---

## Configuration

`config.json` at your CashCrab home directory:

```json
{
  "llm": {
    "provider": "qwen_code",
    "model": "qwen3.5-plus"
  },
  "twitter": {
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "bearer_token": "",
    "schedule_interval_minutes": 60,
    "engage": {
      "keywords": ["AI", "automation", "tech"],
      "max_likes_per_hour": 15,
      "max_replies_per_hour": 5,
      "autopilot_duration_minutes": 30
    },
    "products": [
      {
        "name": "Product Name",
        "url": "https://amzn.to/EXAMPLE",
        "keywords": ["tech"]
      }
    ]
  }
}
```

| Key | What it does |
|---|---|
| `twitter.client_id` | From developer.twitter.com > OAuth 2.0 |
| `twitter.bearer_token` | Optional. Improves read rate limits for engagement |
| `twitter.schedule_interval_minutes` | How often the scheduler runs (default: 60) |
| `twitter.engage.keywords` | Keywords for search & engage + thought leader |
| `twitter.engage.autopilot_duration_minutes` | How long each engagement cycle runs |
| `twitter.products` | Affiliate products for monetization posts |

## Architecture

```text
cashcrab/
├── main.py                 # CLI + interactive menu
├── modules/
│   ├── twitter.py          # Posting, queue, threads, scoring
│   ├── x_engage.py         # Voice AI, engagement, thought leader
│   ├── scheduler.py        # APScheduler (60-min X cycles)
│   ├── llm.py              # Qwen / g4f / Ollama / OpenAI
│   ├── auth.py             # OAuth 2.0 PKCE
│   ├── analytics.py        # Tweet tracking
│   ├── notify.py           # Discord / Slack webhooks
│   ├── config.py           # Config loader
│   └── ui.py               # Terminal UI
├── config.example.json
├── assets/
└── scripts/
    ├── install.sh
    └── install.ps1
```

## License

MIT
