#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import click


def _ui():
    from modules import ui

    return ui


def _run_action(label: str, fn):
    ui = _ui()
    ui.clear()
    ui.banner()
    ui.info(label)
    ui.divider()

    try:
        result = fn()
    except KeyboardInterrupt:
        ui.warn("Cancelled.")
        result = None
    except EOFError:
        ui.warn("Cancelled.")
        result = None
    except SystemExit:
        ui.fail("Setup is incomplete. Fix config.json or the missing keys, then try again.")
        result = None
    except Exception as exc:
        ui.fail(str(exc))
        result = None

    ui.pause()
    return result


def _ask_int(prompt: str, default: int, minimum: int = 1) -> int:
    ui = _ui()
    while True:
        raw = ui.ask(prompt, str(default))
        try:
            value = int(raw)
        except ValueError:
            ui.warn("Please type a whole number.")
            continue
        if value < minimum:
            ui.warn(f"Please type {minimum} or higher.")
            continue
        return value


def _ask_float(prompt: str, default: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    ui = _ui()
    while True:
        raw = ui.ask(prompt, str(default))
        try:
            value = float(raw)
        except ValueError:
            ui.warn("Please type a number.")
            continue
        if not minimum <= value <= maximum:
            ui.warn(f"Please type a number from {minimum} to {maximum}.")
            continue
        return value


def _show_status_dashboard():
    from modules import analytics, auth

    ui = _ui()
    ui.clear()
    ui.banner()
    ui.info("Status")
    ui.divider()
    auth.status()
    if hasattr(analytics, "dashboard"):
        ui.divider()
        analytics.dashboard()
    ui.pause()


def _onboarding_wizard():
    from modules import onboarding

    _run_action("Starting the AI onboarding wizard...", onboarding.run_ai_wizard)


def _repo_workspace_target() -> Path:
    root = Path(__file__).resolve().parent
    if not (root / ".git").exists():
        raise RuntimeError("This command needs the CashCrab git repo root.")
    return root


def _home_workspace_target() -> Path:
    from modules.config import ROOT

    return ROOT / "codex-workspace"


def _skills_agents_menu():
    from modules import agentpacks

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "Skill packs and sub-agents",
            [
                "Show skill categories",
                "List all skill packs",
                "Show one skill pack",
                "List sub-agent roles",
                "Show one sub-agent role",
                "Write skill packs into this repo",
                "Write skill packs into app home",
            ],
            back_label="Back to main menu",
        )

        if choice == 0:
            return
        if choice == 1:
            _run_action("Loading skill categories...", agentpacks.print_skill_categories)
        elif choice == 2:
            _run_action("Loading all skill packs...", agentpacks.print_skill_list)
        elif choice == 3:
            slug = ui.ask("Skill slug", "cashcrab-youtube-title-lab")
            _run_action(f"Loading {slug}...", lambda: agentpacks.print_skill_detail(slug))
        elif choice == 4:
            _run_action("Loading sub-agent roles...", agentpacks.print_agent_list)
        elif choice == 5:
            name = ui.ask("Agent role", "explorer")
            _run_action(f"Loading {name}...", lambda: agentpacks.print_agent_detail(name))
        elif choice == 6:
            _run_action(
                "Writing skill packs into this repo...",
                lambda: agentpacks.sync_workspace(_repo_workspace_target()),
            )
        elif choice == 7:
            _run_action(
                "Writing skill packs into app home...",
                lambda: agentpacks.sync_workspace(_home_workspace_target()),
            )


def _auth_menu():
    from modules import auth

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "Setup and account connections",
            [
                "Connect Qwen OAuth (recommended brain)",
                "Connect Twitter / X",
                "Save keys and webhooks",
                "Show setup status",
                "Remove a saved login",
            ],
            back_label="Back to main menu",
        )

        if choice == 0:
            return
        if choice == 1:
            _run_action("Connecting Qwen OAuth...", auth.qwen_login)
        elif choice == 2:
            _run_action("Connecting Twitter / X...", auth.twitter_login)
        elif choice == 3:
            _run_action("Saving API keys...", auth.setup_api_keys)
        elif choice == 4:
            _run_action("Loading status...", auth.status)
        elif choice == 5:
            confirm = _ui().confirm("Remove saved Twitter / X login?", default=False)
            if confirm:
                _run_action("Removing saved login...", lambda: auth.revoke("twitter"))


def _voice_draft(topic: str):
    from modules import x_engage, twitter

    text = x_engage.generate_in_voice(topic)
    score = twitter.score_content(text)
    ui = _ui()
    ui.info(f"Score: {score['score']}/100 ({score['tier']})")
    ui.info(f"Draft: {text}")
    if ui.confirm("Queue this tweet?", default=True):
        twitter.queue_tweet(text, tweet_type="organic", workflow="voice", topic=topic, source="voice-gen")


def _x_engage_menu():
    from modules import x_engage

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "X Engagement Autopilot",
            [
                "Analyze my voice (build style profile)",
                "Generate tweet in my voice",
                "Search & engage (like + reply)",
                "Run Thought Leader agent",
                "Find engagement targets",
                "Post a thread",
                "Score a draft tweet",
                "Show engagement stats",
            ],
            back_label="Back to X menu",
        )

        if choice == 0:
            return
        if choice == 1:
            count = _ask_int("How many tweets to analyze?", 50, minimum=10)
            _run_action("Analyzing your voice...", lambda: x_engage.analyze_voice(count))
        elif choice == 2:
            topic = ui.ask("Topic", "AI automation")
            _run_action("Generating in your voice...", lambda: _voice_draft(topic))
        elif choice == 3:
            raw_kw = ui.ask("Keywords (comma-separated)", "AI, automation, tech")
            keywords = [k.strip() for k in raw_kw.split(",") if k.strip()]
            max_likes = _ask_int("Max likes?", 10)
            max_replies = _ask_int("Max replies?", 3)
            _run_action(
                "Searching and engaging...",
                lambda: x_engage.search_and_engage(keywords, max_likes=max_likes, max_replies=max_replies),
            )
        elif choice == 4:
            raw_kw = ui.ask("Keywords (comma-separated)", "AI, automation, tech")
            keywords = [k.strip() for k in raw_kw.split(",") if k.strip()]
            duration = _ask_int("Duration (minutes)?", 30, minimum=5)
            _run_action(
                "Running Thought Leader agent...",
                lambda: x_engage.thought_leader_cycle(keywords=keywords, duration_minutes=duration),
            )
        elif choice == 5:
            raw_kw = ui.ask("Keywords (comma-separated)", "AI, automation")
            keywords = [k.strip() for k in raw_kw.split(",") if k.strip()]
            _run_action("Finding targets...", lambda: x_engage.find_targets(keywords))
        elif choice == 6:
            from modules import twitter

            topic = ui.ask("Thread topic", "AI automation tips")
            count = _ask_int("How many tweets in thread?", 4, minimum=2)

            def thread_action():
                texts = twitter.generate_thread(topic, count)
                for i, t in enumerate(texts, 1):
                    score = twitter.score_content(t)
                    ui.info(f"  {i}. [{score['tier']}:{score['score']}] {t}")
                if ui.confirm("Post this thread now?", default=True):
                    twitter.post_thread(texts)
                else:
                    twitter.queue_thread(topic, count)

            _run_action("Generating thread...", thread_action)
        elif choice == 7:
            from modules import twitter

            text = ui.ask("Tweet text to score")
            result = twitter.score_content(text)
            ui.info(f"Score: {result['score']}/100 ({result['tier']})")
            for r in result["reasons"]:
                ui.info(f"  {r}")
            ui.pause()
        elif choice == 8:
            _run_action("Loading engagement stats...", x_engage.engagement_summary)


def _twitter_menu():
    from modules import auth, twitter

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "Twitter / X",
            [
                "X Engagement Autopilot",
                "Build an X workflow queue",
                "Show queued X posts",
                "Post queued X posts now",
                "Draft one post and save it to the queue",
                "Post a mixed batch",
                "Post one helpful tweet",
                "Post one affiliate tweet",
                "Post exact text",
                "Export X queue as Markdown",
                "Connect Twitter / X",
            ],
            back_label="Back to main menu",
        )

        if choice == 0:
            return
        if choice == 1:
            _x_engage_menu()
        elif choice == 2:
            preset = ui.ask("Workflow preset", "authority")
            topic = ui.ask("Topic", "AI workflows")
            count = _ask_int("How many posts?", 3)
            spacing = _ask_int("Minutes between queued posts?", 45)
            _run_action(
                "Building your X workflow queue...",
                lambda: twitter.build_workflow_queue(
                    preset=preset,
                    topic=topic,
                    count=count,
                    spacing_minutes=spacing,
                ),
            )
        elif choice == 3:
            _run_action("Loading the X queue...", twitter.show_queue)
        elif choice == 4:
            limit = _ask_int("How many queued posts should go out now?", 1)
            include_scheduled = ui.confirm("Ignore the scheduled times and force-send them?", default=False)
            _run_action(
                "Posting queued X posts...",
                lambda: twitter.post_queued(limit=limit, include_scheduled=include_scheduled),
            )
        elif choice == 5:
            topic = ui.ask_or_skip("Topic")
            tweet_type = ui.ask("Post type", "organic").strip().lower() or "organic"
            angle = ui.ask_or_skip("Angle or style note") or ""

            def draft_and_queue():
                text = twitter.draft_post(topic=topic, tweet_type=tweet_type, angle=angle)
                twitter.queue_tweet(text, tweet_type=tweet_type, workflow="manual", topic=topic or "")
                ui.info(text)

            _run_action("Drafting and queuing an X post...", draft_and_queue)
        elif choice == 6:
            count = _ask_int("How many tweets?", 1)
            ratio = _ask_float("Affiliate ratio", 0.3)
            _run_action(
                "Posting tweets...",
                lambda: twitter.run_batch(count=count, affiliate_ratio=ratio),
            )
        elif choice == 7:
            topic = ui.ask_or_skip("Topic")
            _run_action("Posting a helpful tweet...", lambda: twitter.post_organic(topic))
        elif choice == 8:
            _run_action("Posting an affiliate tweet...", twitter.post_affiliate)
        elif choice == 9:
            text = ui.ask("Tweet text")
            _run_action("Posting your tweet...", lambda: twitter.post_tweet(text))
        elif choice == 10:
            output = ui.ask("Output file", "x-queue.md")
            _run_action("Exporting the X queue...", lambda: twitter.export_queue(output))
        elif choice == 11:
            _run_action("Connecting Twitter / X...", auth.twitter_login)


def _automation_menu():
    from modules import scheduler

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "Automation",
            [
                "Run X autopilot once",
                "Start the always-on scheduler",
            ],
            back_label="Back to main menu",
        )

        if choice == 0:
            return
        if choice == 1:
            tweets = _ask_int("How many tweets?", 3)
            ratio = _ask_float("Affiliate ratio", 0.3)
            engage = ui.confirm("Also run engagement cycle?", default=True)

            def run_once():
                from modules import twitter, x_engage

                twitter.run_batch(count=tweets, affiliate_ratio=ratio)
                if engage:
                    x_engage.thought_leader_cycle(duration_minutes=30)

            _run_action("Running X autopilot...", run_once)
        elif choice == 2:
            _run_action("Starting the scheduler...", scheduler.start)


def _interactive_menu():
    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "Main menu",
            [
                "Twitter / X",
                "Automation",
                "Setup accounts and API keys",
                "AI setup wizard",
                "Skill packs and sub-agents",
                "Status dashboard",
            ],
            back_label="Exit CashCrab",
        )

        if choice == 0:
            ui.clear()
            return
        if choice == 1:
            _twitter_menu()
        elif choice == 2:
            _automation_menu()
        elif choice == 3:
            _auth_menu()
        elif choice == 4:
            _onboarding_wizard()
        elif choice == 5:
            _skills_agents_menu()
        elif choice == 6:
            _show_status_dashboard()


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx: click.Context):
    """CashCrab - X engagement autopilot from the terminal."""
    if ctx.invoked_subcommand is None:
        _interactive_menu()


@cli.command()
def onboard():
    """Run the AI-guided setup wizard."""
    from modules import onboarding

    onboarding.run_ai_wizard()


@cli.group()
def owner():
    """Owner-side backend and proxy helpers."""
    pass


@owner.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8787, type=int, show_default=True)
def owner_serve(host, port):
    """Run the owner backend/proxy API."""
    from modules import owner_api

    owner_api.run_server(host=host, port=port)


@owner.command("status")
def owner_status():
    """Show local owner backend capability status from environment."""
    from modules import owner_api

    click.echo(json.dumps(owner_api.status_payload(), indent=2))


@cli.group()
def auth():
    """Manage OAuth tokens and API keys."""
    pass


@auth.command()
def qwen():
    """Link Qwen Code OAuth and set it as the recommended LLM."""
    from modules.auth import qwen_login

    qwen_login()


@auth.command()
def twitter():
    """Link your Twitter/X account (OAuth2 PKCE browser flow)."""
    from modules.auth import twitter_login

    twitter_login()


@auth.command()
def keys():
    """Set API keys."""
    from modules.auth import setup_api_keys

    setup_api_keys()


@auth.command()
def status():
    """Show auth status for all services."""
    from modules.auth import status as auth_status

    auth_status()


@auth.command()
@click.argument("service", type=click.Choice(["twitter"]))
def revoke(service):
    """Remove stored tokens for a service."""
    from modules.auth import revoke as auth_revoke

    auth_revoke(service)


@cli.group()
def tw():
    """Twitter / X queue, workflows, posting, and engagement."""
    pass


@tw.command()
@click.option("--count", default=1, help="Number of tweets")
@click.option("--affiliate-ratio", default=0.3, help="Ratio of affiliate vs organic tweets")
def post(count, affiliate_ratio):
    """Post tweet(s)."""
    from modules import twitter

    twitter.run_batch(count, affiliate_ratio)


@tw.command()
@click.argument("text")
def raw(text):
    """Post a specific tweet."""
    from modules import twitter

    twitter.post_tweet(text)


@tw.command()
@click.option("--topic", default=None, help="Tweet topic")
def organic(topic):
    """Post an organic (non-affiliate) tweet."""
    from modules import twitter

    twitter.post_organic(topic)


@tw.command()
def affiliate():
    """Post an affiliate tweet for a random product."""
    from modules import twitter

    twitter.post_affiliate()


@tw.command("draft")
@click.option("--topic", default=None, help="Topic or idea for the post")
@click.option("--type", "tweet_type", default="organic", type=click.Choice(["organic", "affiliate"]))
@click.option("--angle", default="", help="Optional angle or style note")
@click.option("--queue/--no-queue", "save_to_queue", default=True, help="Save the draft into the X queue")
def tw_draft(topic, tweet_type, angle, save_to_queue):
    """Draft one X post, optionally saving it to the queue."""
    from modules import twitter

    text = twitter.draft_post(topic=topic, tweet_type=tweet_type, angle=angle)
    if save_to_queue:
        twitter.queue_tweet(text, tweet_type=tweet_type, workflow="manual", topic=topic or "")
    click.echo(text)


@tw.command("queue")
@click.option("--preset", default="authority", help="Workflow preset")
@click.option("--topic", required=True, help="What the workflow is about")
@click.option("--count", default=3, help="How many posts to create")
@click.option("--spacing-minutes", default=45, help="Minutes between queued posts")
def tw_queue(preset, topic, count, spacing_minutes):
    """Build a queue of X posts from a workflow preset."""
    from modules import twitter

    twitter.build_workflow_queue(
        preset=preset,
        topic=topic,
        count=count,
        spacing_minutes=spacing_minutes,
    )


@tw.command("queue-list")
@click.option("--all", "show_all", is_flag=True, help="Show posted and failed items too")
def tw_queue_list(show_all):
    """Show the local X queue."""
    from modules import twitter

    twitter.show_queue(status=None if show_all else "queued")


@tw.command("post-queued")
@click.option("--limit", default=1, help="How many queued posts to send")
@click.option("--include-scheduled", is_flag=True, help="Ignore schedule times and send anyway")
def tw_post_queued(limit, include_scheduled):
    """Send queued X posts."""
    from modules import twitter

    twitter.post_queued(limit=limit, include_scheduled=include_scheduled)


@tw.command("export-queue")
@click.option("--output", default="x-queue.md", help="Markdown export path")
def tw_export_queue(output):
    """Export the local X queue as Markdown."""
    from modules import twitter

    twitter.export_queue(output)


@tw.command("voice-analyze")
@click.option("--count", default=50, help="Number of tweets to analyze")
def tw_voice_analyze(count):
    """Analyze your writing voice from recent tweets."""
    from modules import x_engage

    x_engage.analyze_voice(count)


@tw.command("voice-post")
@click.option("--topic", required=True, help="Topic to write about")
@click.option("--post/--no-post", default=False, help="Post immediately instead of queuing")
def tw_voice_post(topic, post):
    """Generate and post a tweet matching your voice profile."""
    from modules import x_engage, twitter

    text = x_engage.generate_in_voice(topic)
    score = twitter.score_content(text)
    click.echo(f"[{score['tier']}:{score['score']}] {text}")
    if post:
        twitter.post_tweet(text)
    else:
        twitter.queue_tweet(text, tweet_type="organic", workflow="voice", topic=topic, source="voice-gen")
        click.echo("Queued.")


@tw.command("engage")
@click.option("--keywords", required=True, help="Comma-separated keywords to search")
@click.option("--max-likes", default=10, help="Max likes per run")
@click.option("--max-replies", default=3, help="Max AI replies per run")
def tw_engage(keywords, max_likes, max_replies):
    """Search tweets by keywords and auto-engage (like + AI reply)."""
    from modules import x_engage

    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    x_engage.search_and_engage(kw_list, max_likes=max_likes, max_replies=max_replies)


@tw.command("autopilot")
@click.option("--keywords", default=None, help="Comma-separated keywords (uses config if empty)")
@click.option("--duration", default=30, help="Run duration in minutes")
@click.option("--max-posts", default=2, help="Max original posts per cycle")
@click.option("--max-likes", default=15, help="Max likes per cycle")
@click.option("--max-replies", default=5, help="Max replies per cycle")
def tw_autopilot(keywords, duration, max_posts, max_likes, max_replies):
    """Run the Thought Leader agent (autonomous engagement loop)."""
    from modules import x_engage

    kw_list = None
    if keywords:
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    x_engage.thought_leader_cycle(
        keywords=kw_list,
        duration_minutes=duration,
        max_posts=max_posts,
        max_likes=max_likes,
        max_replies=max_replies,
    )


@tw.command("targets")
@click.option("--keywords", required=True, help="Comma-separated keywords")
@click.option("--min-followers", default=500, help="Min follower count")
@click.option("--max-followers", default=50000, help="Max follower count")
@click.option("--limit", default=20, help="Max targets to return")
def tw_targets(keywords, min_followers, max_followers, limit):
    """Find accounts worth engaging with."""
    from modules import x_engage

    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    x_engage.find_targets(kw_list, min_followers=min_followers, max_followers=max_followers, limit=limit)


@tw.command("thread")
@click.option("--topic", required=True, help="Thread topic")
@click.option("--count", default=4, help="Number of tweets in thread")
@click.option("--post/--no-post", "post_now", default=False, help="Post immediately")
def tw_thread(topic, count, post_now):
    """Generate and post/queue a thread."""
    from modules import twitter

    texts = twitter.generate_thread(topic, count)
    for i, t in enumerate(texts, 1):
        score = twitter.score_content(t)
        click.echo(f"  {i}. [{score['tier']}:{score['score']}] {t}")
    if post_now:
        twitter.post_thread(texts)
    else:
        twitter.queue_thread(topic, count)


@tw.command("score")
@click.argument("text")
def tw_score(text):
    """Score a tweet draft (0-100) without posting."""
    from modules import twitter

    result = twitter.score_content(text)
    click.echo(f"Score: {result['score']}/100 ({result['tier']})")
    for r in result["reasons"]:
        click.echo(f"  {r}")


@tw.command("engage-stats")
def tw_engage_stats():
    """Show engagement activity summary."""
    from modules import x_engage

    x_engage.engagement_summary()


@cli.group(invoke_without_command=True)
@click.pass_context
def skills(ctx):
    """Browse or sync CashCrab skill packs."""
    from modules import agentpacks

    if ctx.invoked_subcommand is None:
        agentpacks.print_skill_categories()


@skills.command("list")
@click.option("--category", default=None, help="Optional skill category key")
def skills_list(category):
    """List available skill packs."""
    from modules import agentpacks

    agentpacks.print_skill_list(category)


@skills.command("show")
@click.argument("slug")
def skills_show(slug):
    """Show one skill pack."""
    from modules import agentpacks

    agentpacks.print_skill_detail(slug)


@skills.command("sync")
@click.option("--target", type=click.Choice(["repo", "home"]), default="repo", show_default=True)
def skills_sync(target):
    """Write skill packs and agent roles into a workspace."""
    from modules import agentpacks

    workspace = _repo_workspace_target() if target == "repo" else _home_workspace_target()
    result = agentpacks.sync_workspace(workspace)
    click.echo(f"Synced {result['skills']} skills and {result['agents']} agents into {workspace}")


@cli.group(invoke_without_command=True)
@click.pass_context
def agents(ctx):
    """Browse CashCrab sub-agent roles."""
    from modules import agentpacks

    if ctx.invoked_subcommand is None:
        agentpacks.print_agent_list()


@agents.command("show")
@click.argument("name")
def agents_show(name):
    """Show one sub-agent role."""
    from modules import agentpacks

    agentpacks.print_agent_detail(name)


@cli.command()
def schedule():
    """Run the scheduler (X posting + engagement on autopilot)."""
    from modules import scheduler

    scheduler.start()


@cli.command()
@click.option("--tweets", default=3, help="Number of tweets to post")
@click.option("--affiliate-ratio", default=0.3, help="Affiliate vs organic ratio")
@click.option("--engage/--no-engage", default=True, help="Also run engagement cycle")
@click.option("--engage-duration", default=30, help="Engagement cycle duration in minutes")
def auto(tweets, affiliate_ratio, engage, engage_duration):
    """Run X autopilot once: tweets + engagement cycle."""
    from modules import twitter, x_engage

    twitter.run_batch(tweets, affiliate_ratio=affiliate_ratio)
    if engage:
        x_engage.thought_leader_cycle(duration_minutes=engage_duration)


@cli.command()
@click.option("--export", "export_path", default=None, help="Optional CSV export path")
def dashboard(export_path):
    """Show the status dashboard."""
    from modules import analytics, auth

    if export_path:
        path = analytics.export_csv(export_path)
        click.echo(f"Exported analytics to {path}")

    auth.status()
    analytics.dashboard()


if __name__ == "__main__":
    cli()
