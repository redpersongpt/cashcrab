"""CashCrab skill catalog and Codex workspace scaffolding."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.table import Table

from modules import ui


@dataclass(frozen=True)
class SkillDefinition:
    slug: str
    name: str
    category: str
    category_title: str
    summary: str
    deliverable: str
    command_hint: str


@dataclass(frozen=True)
class AgentRole:
    name: str
    title: str
    description: str
    ownership: str
    reasoning_effort: str
    model: str
    prompt: str


CATEGORY_TITLES = {
    "youtube": "YouTube Shorts",
    "twitter": "Twitter / X",
    "reels": "TikTok + Instagram",
    "leadgen": "Lead Generation",
    "local-seo": "Local SEO",
    "content": "Content Systems",
    "sales": "Sales",
    "research": "Research",
    "automation": "Automation",
    "analytics": "Analytics",
    "ecommerce": "E-commerce",
    "ops": "Operations",
}


SKILL_BLUEPRINTS = {
    "youtube": [
        ("title-lab", "Title Lab", "Find stronger Shorts title angles and hooks.", "10 title options with 3 hook variants.", "cashcrab yt generate --topic \"...\""),
        ("hook-surgeon", "Hook Surgeon", "Rebuild weak first three seconds into a sharper opening.", "A tighter cold open and subtitle-first hook.", "cashcrab yt generate --topic \"...\" --no-upload"),
        ("script-factory", "Script Factory", "Turn a niche topic into a punchy under-60-second script.", "A ready-to-record Short script.", "cashcrab yt generate --topic \"...\""),
        ("retention-audit", "Retention Audit", "Spot draggy beats and dead air in a Short concept.", "A cut list with pacing fixes.", "cashcrab yt status"),
        ("metadata-stack", "Metadata Stack", "Package title, description, CTA, and hashtags together.", "Upload-ready metadata stack.", "cashcrab yt upload-all"),
        ("affiliate-angle", "Affiliate Angle", "Find a money angle that does not tank trust.", "Affiliate-friendly script notes and CTA.", "cashcrab tw affiliate"),
        ("trend-radar", "Trend Radar", "Map current creator angles into reusable Short topics.", "A ranked topic list with difficulty notes.", "cashcrab yt generate"),
        ("comment-miner", "Comment Miner", "Pull objections and questions worth turning into videos.", "A backlog of Short prompts from audience pain.", "cashcrab dashboard"),
        ("series-planner", "Series Planner", "Break one theme into a multi-video sequence.", "A 7-video Shorts series plan.", "cashcrab auto --shorts 7"),
        ("upload-qa", "Upload QA", "Check whether a Short is actually ready to publish.", "A publish checklist with blocker flags.", "cashcrab yt upload-all"),
    ],
    "twitter": [
        ("thread-smith", "Thread Smith", "Expand one idea into a tight thread.", "A 5-7 post thread draft.", "cashcrab tw organic --topic \"...\""),
        ("reply-hunter", "Reply Hunter", "Find reply angles that can farm attention without being cringe.", "10 reply starters and when to use them.", "cashcrab tw raw \"...\""),
        ("affiliate-balance", "Affiliate Balance", "Push monetized posts without sounding desperate.", "A ratio plan and post sequence.", "cashcrab tw post --count 5 --affiliate-ratio 0.3"),
        ("launch-burst", "Launch Burst", "Turn one launch into a multi-post release day plan.", "A timed launch queue.", "cashcrab tw post --count 10 --affiliate-ratio 0.2"),
        ("controversy-filter", "Controversy Filter", "Sharpen a bold take without making it stupid.", "Safer contrarian copy.", "cashcrab tw organic --topic \"...\""),
        ("thread-recut", "Thread Recut", "Rewrite rambling posts into cleaner sequencing.", "A tighter rewritten thread.", "cashcrab tw raw \"...\""),
        ("quote-tweet-kit", "Quote Tweet Kit", "Prepare quote-tweet reactions for recurring topics.", "10 quote-tweet templates.", "cashcrab tw raw \"...\""),
        ("engagement-loop", "Engagement Loop", "Plan follow-up posts that convert impressions into replies.", "A three-day engagement loop.", "cashcrab tw post --count 3"),
        ("founder-voice", "Founder Voice", "Make posts sound like an operator, not a copy bot.", "Voice rules and rewrites.", "cashcrab tw organic --topic \"...\""),
        ("offer-tweetpack", "Offer Tweetpack", "Package an offer into a small tweet campaign.", "A tweet pack with CTAs and proof points.", "cashcrab tw affiliate"),
    ],
    "reels": [
        ("reel-hooker", "Reel Hooker", "Open Reels harder so viewers do not swipe.", "Hook lines plus on-screen text.", "cashcrab ig upload-latest --caption \"...\" --public-url \"...\""),
        ("caption-engine", "Caption Engine", "Write tighter captions for TikTok and Instagram.", "Platform-fit captions with CTAs.", "cashcrab ig upload-latest --caption \"...\" --public-url \"...\""),
        ("trend-remix", "Trend Remix", "Adapt trends into something that still fits the offer.", "Trend-safe content concepts.", "cashcrab tt upload-latest --title \"...\""),
        ("ugc-brief", "UGC Brief", "Turn a product or service into a creator brief.", "A UGC brief with shots and talking points.", "cashcrab yt generate --topic \"...\""),
        ("comment-farming", "Comment Farming", "Shape posts for saves, comments, and DM triggers.", "A CTA and response plan.", "cashcrab ig upload-latest --caption \"...\" --public-url \"...\""),
        ("story-sequence", "Story Sequence", "Build a short Instagram Story arc around one offer.", "A 5-story sequence with stickers and CTAs.", "cashcrab ig upload-latest --caption \"...\" --public-url \"...\""),
        ("crosspost-fit", "Crosspost Fit", "Adjust a YouTube Short before pushing it elsewhere.", "Cross-post notes by platform.", "cashcrab yt generate --crosspost-tiktok --crosspost-instagram"),
        ("duet-seeder", "Duet Seeder", "Create duet or stitch prompts from a niche topic.", "A duet-ready angle list.", "cashcrab tt upload-latest --title \"...\""),
        ("cta-optimizer", "CTA Optimizer", "Make the ask feel natural instead of needy.", "Better CTA lines and placement notes.", "cashcrab tt upload-latest --title \"...\""),
        ("repost-window", "Repost Window", "Plan timing and copy tweaks for reposting winners.", "A repost calendar.", "cashcrab auto --shorts 3 --crosspost-tiktok --crosspost-instagram"),
    ],
    "leadgen": [
        ("icp-builder", "ICP Builder", "Turn vague buyer ideas into an actual prospect profile.", "A clean ICP brief.", "cashcrab leads find --query \"...\" --location \"...\""),
        ("geo-hunter", "Geo Hunter", "Map local search zones worth scraping first.", "A ranked geo list with demand notes.", "cashcrab leads find --query \"...\" --location \"...\""),
        ("email-finder", "Email Finder", "Prioritize reachable contacts, not vanity names.", "A contact list with confidence notes.", "cashcrab leads outreach --csv leads.csv --dry-run"),
        ("serp-miner", "SERP Miner", "Use search intent to uncover better business targets.", "A better prospect list from SERP cues.", "cashcrab leads find --query \"...\""),
        ("lead-scorer", "Lead Scorer", "Rank prospects by fit, urgency, and buying signal.", "A scored lead sheet.", "cashcrab leads campaign-update campaign-123 --opened 12 --replied 3"),
        ("outreach-personalizer", "Outreach Personalizer", "Write first lines that mention something real.", "A personalization matrix.", "cashcrab leads outreach --csv leads.csv --dry-run"),
        ("campaign-tracker", "Campaign Tracker", "Set the minimum analytics needed to know if outreach works.", "A campaign measurement plan.", "cashcrab dashboard"),
        ("offer-matcher", "Offer Matcher", "Match the right offer to the right local business.", "A lead-to-offer map.", "cashcrab leads find --query \"...\" --location \"...\""),
        ("teaser-audit", "Teaser Audit", "Create a free mini-audit that earns replies.", "A short audit teaser template.", "cashcrab leads outreach --csv leads.csv --dry-run"),
        ("followup-ladder", "Follow-Up Ladder", "Stack follow-ups that escalate value instead of annoyance.", "A 5-touch follow-up sequence.", "cashcrab leads outreach --csv leads.csv --send"),
    ],
    "local-seo": [
        ("gmb-auditor", "GMB Auditor", "Spot obvious Google Business Profile holes fast.", "A local visibility audit.", "cashcrab leads find --query \"...\" --location \"...\""),
        ("review-responder", "Review Responder", "Draft review replies that sound human and local.", "Positive and negative review reply bank.", "cashcrab leads outreach --csv leads.csv --dry-run"),
        ("citation-gap", "Citation Gap", "Find missing or inconsistent local listings.", "A citation cleanup checklist.", "cashcrab leads find --query \"...\" --location \"...\""),
        ("geo-keyword-cluster", "Geo Keyword Cluster", "Break one city offer into surrounding geo pages.", "A local keyword cluster.", "cashcrab leads find --query \"...\" --location \"...\""),
        ("faq-builder", "FAQ Builder", "Create local FAQ blocks that capture buying intent.", "A FAQ section with schema-ready answers.", "cashcrab yt generate --topic \"...\""),
        ("map-pack-tracker", "Map Pack Tracker", "Track which businesses dominate the map pack and why.", "A local competitor snapshot.", "cashcrab dashboard"),
        ("offer-angle", "Offer Angle", "Position a local offer around speed, trust, or proof.", "Three local offer angles.", "cashcrab leads outreach --csv leads.csv --dry-run"),
        ("schema-pack", "Schema Pack", "Draft the schema fields a local page should include.", "A schema implementation brief.", "cashcrab dashboard"),
        ("competitor-map", "Competitor Map", "Compare nearby competitors by proof and positioning.", "A local competitor table.", "cashcrab leads find --query \"...\" --location \"...\""),
        ("local-landing", "Local Landing", "Outline a location page that can actually rank and convert.", "A local landing page outline.", "cashcrab yt generate --topic \"...\""),
    ],
    "content": [
        ("blog-brief", "Blog Brief", "Turn a keyword into a usable article brief.", "A content brief with angle and structure.", "cashcrab yt generate --topic \"...\""),
        ("outline-machine", "Outline Machine", "Cut fluff before it reaches the draft stage.", "A cleaner outline.", "cashcrab yt generate --topic \"...\""),
        ("first-draft", "First Draft", "Get an ugly but usable first draft on the page fast.", "A first-pass article or page.", "cashcrab yt generate --topic \"...\""),
        ("rewrite-harsh", "Rewrite Harsh", "Rewrite soft copy into sharper, leaner copy.", "A tighter rewrite.", "cashcrab tw raw \"...\""),
        ("newsletter-engine", "Newsletter Engine", "Turn updates into a readable newsletter.", "A newsletter issue draft.", "cashcrab tw organic --topic \"...\""),
        ("case-study", "Case Study", "Structure proof into a stronger before/after story.", "A case study draft.", "cashcrab dashboard"),
        ("landing-copy", "Landing Copy", "Write a clearer headline stack and offer section.", "Landing page copy blocks.", "cashcrab leads outreach --csv leads.csv --dry-run"),
        ("ad-copy", "Ad Copy", "Generate multiple paid-ad message angles.", "Ad copy variants.", "cashcrab tw affiliate"),
        ("faq-engine", "FAQ Engine", "Answer objections before they become support tickets.", "A FAQ block.", "cashcrab dashboard"),
        ("proof-puller", "Proof Puller", "Extract proof points hidden in messy notes.", "A proof bank for sales copy.", "cashcrab dashboard"),
    ],
    "sales": [
        ("offer-crafter", "Offer Crafter", "Make the offer easier to say yes to.", "A sharper offer stack.", "cashcrab leads outreach --csv leads.csv --dry-run"),
        ("proposal-writer", "Proposal Writer", "Turn discovery notes into a proposal with spine.", "A scoped proposal.", "cashcrab leads outreach --csv leads.csv --dry-run"),
        ("pricing-matrix", "Pricing Matrix", "Separate starter, standard, and premium work clearly.", "A pricing ladder.", "cashcrab dashboard"),
        ("objection-handler", "Objection Handler", "Prepare answers for price, trust, and timing objections.", "An objection-handling doc.", "cashcrab leads outreach --csv leads.csv --dry-run"),
        ("close-plan", "Close Plan", "Map the shortest path from interest to paid work.", "A close plan with next-step CTAs.", "cashcrab leads outreach --csv leads.csv --send"),
        ("upsell-map", "Upsell Map", "Sequence the next offer after the first win.", "An upsell roadmap.", "cashcrab dashboard"),
        ("retainer-pitch", "Retainer Pitch", "Package repeat work into a monthly offer.", "A retainer pitch.", "cashcrab auto --find-leads"),
        ("guarantee-designer", "Guarantee Designer", "Add risk reversal without writing checks you cannot cash.", "A safer guarantee set.", "cashcrab dashboard"),
        ("scope-guard", "Scope Guard", "Prevent messy delivery by tightening what is in and out.", "A scope checklist.", "cashcrab dashboard"),
        ("followup-chain", "Follow-Up Chain", "Keep the sale alive after the first no-response.", "A close-focused follow-up chain.", "cashcrab leads outreach --csv leads.csv --send"),
    ],
    "research": [
        ("competitor-scan", "Competitor Scan", "Get the useful bits from competitor research fast.", "A competitor scan.", "cashcrab dashboard"),
        ("pricing-research", "Pricing Research", "Check what similar offers charge and how they package.", "A pricing comparison.", "cashcrab dashboard"),
        ("customer-voice", "Customer Voice", "Mine phrases customers actually use.", "A voice-of-customer bank.", "cashcrab tw organic --topic \"...\""),
        ("pain-cluster", "Pain Cluster", "Group repeated complaints into clear messaging buckets.", "A pain-point cluster map.", "cashcrab dashboard"),
        ("trend-report", "Trend Report", "Find early movement in a niche before it gets crowded.", "A short trend memo.", "cashcrab yt generate --topic \"...\""),
        ("creator-teardown", "Creator Teardown", "Reverse-engineer what makes a creator account work.", "A creator teardown.", "cashcrab dashboard"),
        ("niche-finder", "Niche Finder", "Rank business niches by demand, pain, and content surface area.", "A ranked niche shortlist.", "cashcrab leads find --query \"...\""),
        ("swot-fast", "SWOT Fast", "Do a quick strategic scan without turning it into MBA sludge.", "A fast SWOT.", "cashcrab dashboard"),
        ("angle-gap", "Angle Gap", "Find what nobody else in the niche is saying clearly.", "A messaging gap brief.", "cashcrab tw organic --topic \"...\""),
        ("funnel-audit", "Funnel Audit", "Check where attention dies between content and offer.", "A funnel friction report.", "cashcrab dashboard"),
    ],
    "automation": [
        ("workflow-designer", "Workflow Designer", "Map a repeatable workflow before automating it.", "A workflow map.", "cashcrab schedule"),
        ("webhook-planner", "Webhook Planner", "Define who gets notified and when.", "A webhook routing plan.", "cashcrab schedule"),
        ("scheduler-map", "Scheduler Map", "Break daily, weekly, and monthly jobs apart cleanly.", "A schedule map.", "cashcrab schedule"),
        ("handoff-writer", "Handoff Writer", "Write operator notes that survive context loss.", "A clean handoff template.", "cashcrab dashboard"),
        ("sop-builder", "SOP Builder", "Turn a working flow into an SOP somebody can repeat.", "An SOP draft.", "cashcrab auto --shorts 1 --tweets 3"),
        ("qa-checklist", "QA Checklist", "Define minimum checks before publishing or outreach.", "A QA checklist.", "cashcrab dashboard"),
        ("exception-handler", "Exception Handler", "List failure modes and the fallback move for each.", "An exception playbook.", "cashcrab schedule"),
        ("dashboard-spec", "Dashboard Spec", "Define what should actually be measured.", "A dashboard spec.", "cashcrab dashboard"),
        ("alert-routing", "Alert Routing", "Separate noise from alerts worth waking up for.", "An alert priority map.", "cashcrab schedule"),
        ("backlog-triage", "Backlog Triage", "Rank work by cash impact and effort.", "A triaged backlog.", "cashcrab dashboard"),
    ],
    "analytics": [
        ("kpi-tree", "KPI Tree", "Connect vanity metrics to actual money metrics.", "A KPI tree.", "cashcrab dashboard"),
        ("attribution-notes", "Attribution Notes", "Explain what really drove a result and what did not.", "A short attribution memo.", "cashcrab dashboard"),
        ("cohort-snapshot", "Cohort Snapshot", "Group results by time or source for clearer reads.", "A cohort snapshot.", "cashcrab dashboard --export analytics.csv"),
        ("postmortem-writer", "Postmortem Writer", "Write useful postmortems after a flop or miss.", "A postmortem.", "cashcrab dashboard"),
        ("leaderboard", "Leaderboard", "Rank channels, offers, or creatives by outcome.", "A leaderboard view.", "cashcrab dashboard"),
        ("revenue-mix", "Revenue Mix", "Show which offer types actually carry the business.", "A revenue mix report.", "cashcrab dashboard --export analytics.csv"),
        ("creator-scorecard", "Creator Scorecard", "Score content output by consistency, reach, and conversion.", "A creator scorecard.", "cashcrab dashboard"),
        ("pipeline-health", "Pipeline Health", "Check whether leads and content are feeding enough demand.", "A pipeline health brief.", "cashcrab dashboard"),
        ("content-performance", "Content Performance", "Pinpoint what content angles outperform.", "A content performance summary.", "cashcrab dashboard --export analytics.csv"),
        ("experiment-readout", "Experiment Readout", "Summarize what changed, what happened, and what to do next.", "An experiment readout.", "cashcrab dashboard"),
    ],
    "ecommerce": [
        ("product-angle", "Product Angle", "Frame the product around one clear buying job.", "A message angle sheet.", "cashcrab tw affiliate"),
        ("review-miner", "Review Miner", "Pull proof, objections, and phrasing from reviews.", "A review insight bank.", "cashcrab dashboard"),
        ("pdp-copy", "PDP Copy", "Write cleaner product page copy.", "A product detail page rewrite.", "cashcrab tw affiliate"),
        ("bundle-builder", "Bundle Builder", "Combine items into a more compelling bundle.", "A bundle offer plan.", "cashcrab dashboard"),
        ("offer-stack", "Offer Stack", "Layer bonuses and urgency without looking scammy.", "An offer stack.", "cashcrab tw affiliate"),
        ("upsell-sequence", "Upsell Sequence", "Plan what to show right after checkout.", "A post-purchase upsell sequence.", "cashcrab dashboard"),
        ("cart-recovery", "Cart Recovery", "Write fewer, better recovery messages.", "An abandoned-cart sequence.", "cashcrab dashboard"),
        ("seasonal-campaign", "Seasonal Campaign", "Turn a holiday window into a timed plan.", "A seasonal campaign brief.", "cashcrab tw affiliate"),
        ("creator-outreach", "Creator Outreach", "Prepare a clean creator collab pitch.", "A creator outreach pack.", "cashcrab leads outreach --csv leads.csv --dry-run"),
        ("sku-prioritizer", "SKU Prioritizer", "Focus effort on the products most likely to move.", "A SKU priority sheet.", "cashcrab dashboard"),
    ],
    "ops": [
        ("invoice-followup", "Invoice Follow-Up", "Chase invoices without sounding weak.", "An invoice follow-up sequence.", "cashcrab dashboard"),
        ("cash-forecast", "Cash Forecast", "Estimate near-term revenue and bottlenecks.", "A short cash forecast.", "cashcrab dashboard --export analytics.csv"),
        ("package-profit", "Package Profit", "Check whether an offer makes enough after delivery time.", "A package profitability sheet.", "cashcrab dashboard"),
        ("margin-sanity", "Margin Sanity", "Spot where fulfillment time is killing margin.", "A margin sanity report.", "cashcrab dashboard"),
        ("workload-planner", "Workload Planner", "Map what can fit this week without wrecking delivery.", "A workload plan.", "cashcrab schedule"),
        ("calendar-planner", "Calendar Planner", "Sequence campaigns and delivery windows on one calendar.", "An operating calendar.", "cashcrab schedule"),
        ("winback-campaign", "Winback Campaign", "Build a simple reactivation sequence for old leads.", "A winback campaign.", "cashcrab leads outreach --csv leads.csv --send"),
        ("referral-engine", "Referral Engine", "Ask for referrals at the right time with the right phrasing.", "A referral ask flow.", "cashcrab leads outreach --csv leads.csv --dry-run"),
        ("client-onboarding", "Client Onboarding", "Reduce chaos at the start of a paid engagement.", "A client onboarding checklist.", "cashcrab dashboard"),
        ("delivery-wrapup", "Delivery Wrap-Up", "Close work cleanly and tee up the next offer.", "A delivery wrap-up script.", "cashcrab dashboard"),
    ],
}


SKILLS = [
    SkillDefinition(
        slug=f"cashcrab-{category}-{suffix}",
        name=name,
        category=category,
        category_title=CATEGORY_TITLES[category],
        summary=summary,
        deliverable=deliverable,
        command_hint=command_hint,
    )
    for category, items in SKILL_BLUEPRINTS.items()
    for suffix, name, summary, deliverable, command_hint in items
]

assert len(SKILLS) == 120, f"Expected 120 skills, found {len(SKILLS)}"


AGENTS = [
    AgentRole(
        name="explorer",
        title="Explorer",
        description="Read-only evidence gatherer for code, markets, and operators.",
        ownership="Search, compare, and summarize without mutating the workspace.",
        reasoning_effort="medium",
        model="gpt-5.4",
        prompt="Collect evidence first. Prefer files, docs, and concrete observations over guesses. Do not edit files.",
    ),
    AgentRole(
        name="reviewer",
        title="Reviewer",
        description="Correctness, regression, and security reviewer.",
        ownership="Review plans, diffs, and edge cases before shipping.",
        reasoning_effort="high",
        model="gpt-5.4",
        prompt="Find the bug, the regression, or the missing guardrail. Do not waste cycles on style-only comments.",
    ),
    AgentRole(
        name="docs-researcher",
        title="Docs Researcher",
        description="API and release-note verifier for anything that can drift.",
        ownership="Verify official docs, quotas, endpoints, and package behavior.",
        reasoning_effort="medium",
        model="gpt-5.4",
        prompt="Use primary docs. Quote only what is needed. Flag uncertainty and recent changes clearly.",
    ),
    AgentRole(
        name="content-operator",
        title="Content Operator",
        description="Runs content production loops across Shorts, X, Reels, and offers.",
        ownership="Hooks, scripts, captions, repurposing, and content QA.",
        reasoning_effort="medium",
        model="gpt-5.4",
        prompt="Optimize for attention, clarity, and conversion. Avoid generic creator sludge.",
    ),
    AgentRole(
        name="lead-hunter",
        title="Lead Hunter",
        description="Prospecting specialist for local businesses and outbound workflows.",
        ownership="ICP shaping, lead scoring, outreach angles, and follow-up plans.",
        reasoning_effort="medium",
        model="gpt-5.4",
        prompt="Favor qualified leads over big lists. Keep claims grounded in verifiable signals.",
    ),
    AgentRole(
        name="closer",
        title="Closer",
        description="Turns interest into offers, pricing, proposals, and next steps.",
        ownership="Offer design, objection handling, follow-up, and retainer packaging.",
        reasoning_effort="medium",
        model="gpt-5.4",
        prompt="Make the next step obvious. Protect margin. Remove ambiguity from scope and price.",
    ),
    AgentRole(
        name="automation-operator",
        title="Automation Operator",
        description="Designs schedules, alerts, SOPs, and failure handling.",
        ownership="Operational reliability, job timing, retries, and handoffs.",
        reasoning_effort="medium",
        model="gpt-5.4",
        prompt="Design repeatable systems. Assume failures will happen and define fallback paths.",
    ),
    AgentRole(
        name="revenue-analyst",
        title="Revenue Analyst",
        description="Interprets dashboards, experiments, and pipeline health.",
        ownership="KPI trees, attribution notes, revenue mix, and experiment readouts.",
        reasoning_effort="medium",
        model="gpt-5.4",
        prompt="Reduce vanity metrics to cash and conversion truths. Prefer simple explanations with next actions.",
    ),
]


def categories() -> list[tuple[str, str, int]]:
    rows = []
    for key, title in CATEGORY_TITLES.items():
        count = sum(1 for skill in SKILLS if skill.category == key)
        rows.append((key, title, count))
    return rows


def list_skills(category: str | None = None) -> list[SkillDefinition]:
    if not category:
        return sorted(SKILLS, key=lambda skill: (skill.category_title, skill.name))

    normalized = category.strip().lower()
    return [
        skill
        for skill in sorted(SKILLS, key=lambda item: item.name)
        if skill.category == normalized or skill.category_title.lower() == normalized
    ]


def get_skill(slug: str) -> SkillDefinition | None:
    normalized = slug.strip().lower()
    for skill in SKILLS:
        if skill.slug == normalized:
            return skill
    return None


def list_agents() -> list[AgentRole]:
    return sorted(AGENTS, key=lambda agent: agent.name)


def get_agent(name: str) -> AgentRole | None:
    normalized = name.strip().lower()
    for agent in AGENTS:
        if agent.name == normalized:
            return agent
    return None


def print_skill_categories():
    table = Table(box=box.SIMPLE_HEAVY, padding=(0, 1))
    table.add_column("Key", style="bold cyan")
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right", style="green")

    for key, title, count in categories():
        table.add_row(key, title, str(count))

    ui.console.print()
    ui.console.print(
        Panel(
            table,
            title="[money]CashCrab Skill Categories[/money]",
            subtitle="[dim]120 total skill packs[/dim]",
            border_style="hint",
            box=box.ROUNDED,
        )
    )


def print_skill_list(category: str | None = None):
    skills = list_skills(category)
    title = "CashCrab Skills" if category is None else f"CashCrab Skills: {category}"

    table = Table(box=box.SIMPLE_HEAVY, padding=(0, 1))
    table.add_column("Slug", style="bold cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Category", style="green")
    table.add_column("What It Does", style="dim")

    for skill in skills:
        table.add_row(skill.slug, skill.name, skill.category_title, skill.summary)

    ui.console.print()
    ui.console.print(
        Panel(
            table,
            title=f"[money]{title}[/money]",
            subtitle="[dim]Use `cashcrab skills show <slug>` for detail[/dim]",
            border_style="hint",
            box=box.ROUNDED,
        )
    )


def print_skill_detail(slug: str):
    skill = get_skill(slug)
    if skill is None:
        raise RuntimeError(f"Unknown skill: {slug}")

    body = "\n".join(
        [
            f"[bold]Category:[/bold] {skill.category_title}",
            f"[bold]Skill:[/bold] {skill.name}",
            f"[bold]What it does:[/bold] {skill.summary}",
            f"[bold]Deliverable:[/bold] {skill.deliverable}",
            f"[bold]Native command:[/bold] [cyan]{skill.command_hint}[/cyan]",
        ]
    )

    ui.console.print()
    ui.console.print(
        Panel(
            body,
            title=f"[money]{skill.slug}[/money]",
            border_style="hint",
            box=box.ROUNDED,
        )
    )


def print_agent_list():
    table = Table(box=box.SIMPLE_HEAVY, padding=(0, 1))
    table.add_column("Role", style="bold cyan")
    table.add_column("Model", style="green")
    table.add_column("Effort", style="yellow")
    table.add_column("Ownership", style="dim")

    for agent in list_agents():
        table.add_row(agent.name, agent.model, agent.reasoning_effort, agent.ownership)

    ui.console.print()
    ui.console.print(
        Panel(
            table,
            title="[money]CashCrab Sub-Agent Roles[/money]",
            subtitle="[dim]Use `cashcrab agents show <name>` for detail[/dim]",
            border_style="hint",
            box=box.ROUNDED,
        )
    )


def print_agent_detail(name: str):
    agent = get_agent(name)
    if agent is None:
        raise RuntimeError(f"Unknown agent role: {name}")

    body = "\n".join(
        [
            f"[bold]Role:[/bold] {agent.title}",
            f"[bold]Model:[/bold] {agent.model}",
            f"[bold]Reasoning:[/bold] {agent.reasoning_effort}",
            f"[bold]Description:[/bold] {agent.description}",
            f"[bold]Ownership:[/bold] {agent.ownership}",
            f"[bold]Prompt:[/bold] {agent.prompt}",
        ]
    )

    ui.console.print()
    ui.console.print(
        Panel(
            body,
            title=f"[money]{agent.name}[/money]",
            border_style="hint",
            box=box.ROUNDED,
        )
    )


def _skill_markdown(skill: SkillDefinition) -> str:
    return f"""---
name: {skill.slug}
description: {skill.summary}
---

# {skill.name}

You are a CashCrab skill pack focused on {skill.category_title.lower()} work.

## Mission

{skill.summary}

## What to deliver

- {skill.deliverable}
- One clear recommendation for what to do next
- No filler, no generic AI copy, no fake certainty

## Workflow

1. Clarify the niche, audience, and money goal.
2. Audit what already exists before writing new output.
3. Produce the deliverable in a way the operator can use immediately.
4. Flag weak assumptions and missing inputs instead of guessing.
5. End with the next highest-leverage move.

## Guardrails

- Prefer concrete output over abstract advice.
- Match the tone to the niche; do not sound like a startup brochure.
- Keep outputs biased toward speed, proof, and revenue.
- If the request is underspecified, list the exact assumptions you had to make.

## Native command hint

```bash
{skill.command_hint}
```
"""


def _agent_yaml(skill: SkillDefinition) -> str:
    return "\n".join(
        [
            f"name: {skill.slug}",
            f"description: {skill.summary}",
            "model: gpt-5.4",
            "reasoning_effort: medium",
        ]
    ) + "\n"


def _codex_config_text() -> str:
    lines = [
        "[features]",
        'multi_agent = true',
        "",
    ]

    for agent in list_agents():
        lines.extend(
            [
                f"[agents.{agent.name}]",
                f'description = "{agent.description}"',
                f'config = ".codex/agents/{agent.name}.toml"',
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def _agent_toml(agent: AgentRole) -> str:
    prompt = agent.prompt.replace('"', '\\"')
    ownership = agent.ownership.replace('"', '\\"')
    description = agent.description.replace('"', '\\"')
    return "\n".join(
        [
            f'model = "{agent.model}"',
            f'reasoning_effort = "{agent.reasoning_effort}"',
            f'description = "{description}"',
            f'ownership = "{ownership}"',
            f'instruction = "{prompt}"',
            "",
        ]
    )


def _skills_readme() -> str:
    return "\n".join(
        [
            "# CashCrab Skill Packs",
            "",
            "This directory is generated by CashCrab.",
            "",
            f"- Total skill packs: {len(SKILLS)}",
            f"- Total sub-agent roles: {len(AGENTS)}",
            "",
            "Categories:",
            *[f"- `{key}`: {title} ({count})" for key, title, count in categories()],
            "",
            "Regenerate with:",
            "",
            "```bash",
            "python3 scripts/sync_codex_workspace.py .",
            "```",
            "",
        ]
    )


def sync_workspace(workspace_root: Path) -> dict[str, int]:
    workspace_root = workspace_root.resolve()
    skills_root = workspace_root / ".agents" / "skills"
    codex_agents_root = workspace_root / ".codex" / "agents"

    skills_root.mkdir(parents=True, exist_ok=True)
    codex_agents_root.mkdir(parents=True, exist_ok=True)

    (workspace_root / ".codex" / "config.toml").write_text(_codex_config_text(), encoding="utf-8")
    (skills_root / "README.md").write_text(_skills_readme(), encoding="utf-8")
    (skills_root / "index.json").write_text(
        json.dumps([skill.__dict__ for skill in SKILLS], indent=2) + "\n",
        encoding="utf-8",
    )

    for agent in list_agents():
        (codex_agents_root / f"{agent.name}.toml").write_text(_agent_toml(agent), encoding="utf-8")

    for skill in SKILLS:
        skill_dir = skills_root / skill.slug
        (skill_dir / "agents").mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(_skill_markdown(skill), encoding="utf-8")
        (skill_dir / "agents" / "openai.yaml").write_text(_agent_yaml(skill), encoding="utf-8")

    return {"skills": len(SKILLS), "agents": len(AGENTS)}
