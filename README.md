<p align="center">
  <img src="assets/cashcrab.png" width="280" alt="CashCrab mascot" />
</p>

<h1 align="center">CashCrab</h1>

<p align="center">
  <strong>X engagement autopilot.</strong><br>
  Grow your X account on autopilot. Voice-matched posts, smart replies, threads, quote tweets, and 24/7 autonomous engagement.
</p>

---

## What is CashCrab?

CashCrab is a terminal tool that runs your X (Twitter) account on autopilot. You tell it what your brand is about, it:

1. **Learns your voice** from your past tweets
2. **Posts original tweets** that sound like you, not AI
3. **Replies to relevant conversations** in your niche
4. **Quote tweets** with hot takes and roasts
5. **Likes and follows** relevant accounts
6. **Posts threads** for deeper engagement
7. **Checks for new GitHub releases** and auto-announces them
8. **Runs 24/7 on a server** with smart scheduling (posts more during peak hours, less at night)

Three AI brains available (all free):
- **Codex** (OpenAI o4-mini) - fastest, best for quick replies
- **Gemini** (Google Flash) - creative, good variety
- **Qwen** (Alibaba) - free, no API key needed

CashCrab rotates between them automatically so your content sounds varied and human.

---

## Quickstart (5 minutes)

### Step 1: Install

macOS / Linux / WSL:

```bash
curl -fsSL https://raw.githubusercontent.com/redpersongpt/cashcrab/main/scripts/install.sh | bash
```

Or manually:

```bash
git clone https://github.com/redpersongpt/cashcrab.git
cd cashcrab
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

### Step 2: Connect your X account

**Option A: Browser cookies (easiest, no API keys needed)**

```bash
cashcrab auth twitter-cookies
```

It will ask you for two cookies from your browser. To get them:
1. Open x.com and make sure you're logged in
2. Press F12 (DevTools) > Application tab > Cookies > https://x.com
3. Copy the value of `ct0` and `auth_token`
4. Paste them when asked

**Option B: OAuth (needs Twitter Developer account)**

```bash
cashcrab auth twitter
```

Requires `client_id` and `client_secret` from developer.twitter.com.

### Step 3: Connect an AI brain

```bash
cashcrab auth qwen
```

This opens Qwen OAuth in your browser. Free, no credit card.

Want Gemini too? Install the CLI:
```bash
npm install -g @google/gemini-cli
gemini  # follow the login flow
```

Want Codex too?
```bash
npm install -g @openai/codex
codex   # follow the login flow
```

### Step 4: Analyze your voice

```bash
cashcrab tw voice-analyze --count 50
```

CashCrab reads your last 50 tweets and builds a writing style profile. Every future post will match your exact tone, vocabulary, and vibe.

### Step 5: Run the autopilot

```bash
cashcrab tw autopilot --keywords "AI,tech,startups" --duration 60
```

Or for 24/7 server mode:

```bash
# Start the autonomous agent (runs forever)
python3 scripts/agent_runner.py

# Or with PM2 (recommended for servers)
pm2 start scripts/agent_runner.py --name twitter-agent --interpreter .venv/bin/python3
```

That's it. CashCrab is now running your X account.

---

## What the agent does every cycle

Every 15-30 minutes (adjusts based on time of day):

| Action | What happens | Daily limit |
|--------|-------------|-------------|
| **Tweet** | Generates an original post in your voice about your configured topics | 25/day |
| **Reply** | Searches your keywords, finds relevant tweets, drops helpful/funny replies | 80/day |
| **Quote tweet** | Finds hot takes to quote with your perspective or a roast | 10/day |
| **Thread** | Writes 4-5 tweet threads on your topics (hook > value > CTA) | 3/day |
| **Like** | Likes relevant tweets on timeline and search | 150/day |
| **Follow** | Follows relevant accounts in your niche | 30/day |
| **Mention reply** | Checks notifications, replies to real people (ignores bots/spam) | included in 80 |
| **Release check** | Checks your GitHub repo for new releases, auto-announces | 1 per release |

### Smart scheduling

- **Peak hours** (US/EU daytime): posts more, engages more, follows
- **Normal hours**: standard activity
- **Dead hours** (3-6 AM UTC): just likes and light engagement
- All actions have random human-like delays between them

### Safety

- Every tweet/reply goes through a **safety check** (no wrong claims, no embarrassment)
- Every tweet/reply goes through a **virality check** (boring content gets rejected)
- Bot/spam replies are auto-ignored
- Technical claims only posted if the AI is 100% sure
- Will never post anything political, personal, or off-brand

---

## Configuration

CashCrab reads `config.json` from its home directory. Here's what matters:

```json
{
  "llm": {
    "provider": "qwen_code",
    "model": "qwen3.5-plus",
    "auth_type": "qwen-oauth"
  },
  "twitter": {
    "engage": {
      "keywords": ["AI", "automation", "tech"]
    },
    "products": [
      {
        "name": "Your Product",
        "url": "https://yoursite.com",
        "keywords": ["relevant", "keywords"]
      }
    ]
  },
  "gemini": {
    "enabled": true
  },
  "codex_llm": {
    "enabled": true
  },
  "agent": {
    "product_name": "YourProduct",
    "product_url": "yoursite.com",
    "github_repo": "yourname/yourrepo",
    "tweet_topics": [
      "topic your audience cares about",
      "another topic",
      "a controversial but true fact"
    ],
    "search_queries": [
      "keywords people tweet about",
      "problems your product solves"
    ],
    "relevance_keywords": ["words", "that", "matter"],
    "roast_triggers": ["bad takes to roast"],
    "quote_triggers": ["topics worth quoting"],
    "thread_topics": ["deep dive topics for threads"],
    "follow_targets": ["niche keywords for finding accounts to follow"]
  }
}
```

### Agent config explained

| Key | What it does |
|-----|-------------|
| `product_name` | Your product name. Used in generated content. |
| `product_url` | Link to include in tweets. |
| `github_repo` | `owner/repo` format. Agent checks for new releases. |
| `tweet_topics` | List of topics the agent randomly picks from when writing tweets. Be specific. |
| `search_queries` | What to search on X to find conversations to join. |
| `relevance_keywords` | Words that make a tweet "worth engaging with". |
| `roast_triggers` | Phrases that trigger a roast reply instead of a helpful one. |
| `quote_triggers` | Phrases that make a tweet worth quote-tweeting. |
| `thread_topics` | Topics for multi-tweet threads. |
| `follow_targets` | Keywords for finding accounts to follow. |

---

## All commands

```bash
# Voice & content
cashcrab tw voice-analyze --count 50     # Learn your writing style
cashcrab tw voice-post --topic "AI"      # Post in your voice
cashcrab tw score "draft text"           # Score a draft 0-100
cashcrab tw thread --topic "tips" --post # Post a thread

# Engagement
cashcrab tw engage --keywords "AI,tech"  # Search + like + reply
cashcrab tw targets --keywords "AI"      # Find accounts to engage with
cashcrab tw autopilot --duration 60      # Run engagement loop

# Queue
cashcrab tw draft --topic "AI tips"      # Draft and queue a post
cashcrab tw queue --preset authority     # Build a content queue
cashcrab tw queue-list                   # View queued posts
cashcrab tw post-queued --limit 5        # Send queued posts

# Auth
cashcrab auth qwen                       # Connect Qwen (free AI)
cashcrab auth twitter                    # Connect X (OAuth)
cashcrab auth twitter-cookies            # Connect X (browser cookies)
cashcrab auth keys                       # Set API keys
cashcrab auth status                     # Check connections

# Server
cashcrab schedule                        # Run scheduler loop
cashcrab auto --tweets 3 --engage        # One-shot: post + engage
cashcrab dashboard                       # View analytics
```

---

## Deploy on a server (24/7)

```bash
# On your VDS/VPS:
git clone https://github.com/redpersongpt/cashcrab.git
cd cashcrab
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
playwright install chromium

# Copy your config.json, voice_profile.json, and tokens/ from local
# Then:
pm2 start scripts/agent_runner.py --name twitter-agent --interpreter .venv/bin/python3
pm2 save
pm2 startup  # auto-start on reboot
```

Monitor:
```bash
pm2 logs twitter-agent          # Live logs
pm2 status                      # Process status
cat agent_analytics.json        # Daily stats
```

---

## Architecture

```
cashcrab/
├── main.py                      # CLI + interactive menu
├── modules/
│   ├── twitter.py               # Posting, queue, threads, scoring
│   ├── x_engage.py              # Voice AI, engagement, thought leader
│   ├── twitter_agent.py         # 24/7 autonomous agent (the brain)
│   ├── twikit_client.py         # Cookie-based X client (no API keys)
│   ├── llm.py                   # Triple-LLM: Codex + Gemini + Qwen
│   ├── scheduler.py             # APScheduler
│   ├── auth.py                  # OAuth 2.0 + cookie auth
│   ├── analytics.py             # Tweet tracking
│   ├── notify.py                # Discord / Slack webhooks
│   ├── config.py                # Config loader
│   └── ui.py                    # Terminal UI
├── scripts/
│   ├── agent_runner.py          # 24/7 server runner (PM2 compatible)
│   ├── install.sh               # macOS/Linux installer
│   └── install.ps1              # Windows installer
├── config.example.json
└── assets/
```

## License

MIT
