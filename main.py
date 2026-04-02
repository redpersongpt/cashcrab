#!/usr/bin/env python3
from __future__ import annotations

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
    from modules import analytics, auth, youtube

    ui = _ui()
    ui.clear()
    ui.banner()
    ui.info("Status")
    ui.divider()
    auth.status()
    ui.divider()
    youtube.status()
    if hasattr(analytics, "dashboard"):
        ui.divider()
        analytics.dashboard()
    ui.pause()


def _auth_menu():
    from modules import auth

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "Setup and account connections",
            [
                "Connect YouTube",
                "Connect Twitter / X",
                "Save API keys",
                "Show setup status",
                "Remove a saved login",
            ],
            back_label="Back to main menu",
        )

        if choice == 0:
            return
        if choice == 1:
            _run_action("Connecting YouTube...", auth.youtube_login)
        elif choice == 2:
            _run_action("Connecting Twitter / X...", auth.twitter_login)
        elif choice == 3:
            _run_action("Saving API keys...", auth.setup_api_keys)
        elif choice == 4:
            _run_action("Loading status...", auth.status)
        elif choice == 5:
            service_choice = None

            def revoke_prompt():
                nonlocal service_choice
                local_ui = _ui()
                service_choice = local_ui.menu(
                    "Which saved login should be removed?",
                    ["YouTube", "Twitter / X"],
                    back_label="Cancel",
                )
                if service_choice == 1:
                    auth.revoke("youtube")
                elif service_choice == 2:
                    auth.revoke("twitter")

            _run_action("Removing saved login...", revoke_prompt)


def _youtube_menu():
    from modules import auth, video, youtube

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "YouTube Shorts",
            [
                "Make one Short and upload it",
                "Make one Short without uploading",
                "Upload any pending Shorts",
                "Show Shorts status",
                "Connect YouTube",
            ],
            back_label="Back to main menu",
        )

        if choice == 0:
            return
        if choice == 1:
            topic = ui.ask_or_skip("Topic")

            def generate_and_upload():
                result = video.generate_short(topic)
                youtube.upload(result["video_path"], result["title"], result["description"])

            _run_action("Making and uploading a YouTube Short...", generate_and_upload)
        elif choice == 2:
            topic = ui.ask_or_skip("Topic")
            _run_action("Making a YouTube Short...", lambda: video.generate_short(topic))
        elif choice == 3:
            _run_action("Uploading pending Shorts...", youtube.upload_pending)
        elif choice == 4:
            _run_action("Loading Shorts status...", youtube.status)
        elif choice == 5:
            _run_action("Connecting YouTube...", auth.youtube_login)


def _twitter_menu():
    from modules import auth, twitter

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "Twitter / X",
            [
                "Post a mixed batch",
                "Post one helpful tweet",
                "Post one affiliate tweet",
                "Post exact text",
                "Connect Twitter / X",
            ],
            back_label="Back to main menu",
        )

        if choice == 0:
            return
        if choice == 1:
            count = _ask_int("How many tweets?", 1)
            ratio = _ask_float("Affiliate ratio", 0.3)
            _run_action(
                "Posting tweets...",
                lambda: twitter.run_batch(count=count, affiliate_ratio=ratio),
            )
        elif choice == 2:
            topic = ui.ask_or_skip("Topic")
            _run_action("Posting a helpful tweet...", lambda: twitter.post_organic(topic))
        elif choice == 3:
            _run_action("Posting an affiliate tweet...", twitter.post_affiliate)
        elif choice == 4:
            text = ui.ask("Tweet text")
            _run_action("Posting your tweet...", lambda: twitter.post_tweet(text))
        elif choice == 5:
            _run_action("Connecting Twitter / X...", auth.twitter_login)


def _leads_menu():
    from modules import auth, leads as leads_mod

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "Lead finder and outreach",
            [
                "Find leads and save them to CSV",
                "Preview outreach emails",
                "Send outreach emails",
                "Save Google Places key",
            ],
            back_label="Back to main menu",
        )

        if choice == 0:
            return
        if choice == 1:
            query = ui.ask_or_skip("Business type")
            location = ui.ask_or_skip("City or area")
            output = ui.ask_or_skip("CSV file path")

            def find_and_export():
                results = leads_mod.find_leads(query, location)
                leads_mod.export_csv(results, output)

            _run_action("Finding leads...", find_and_export)
        elif choice == 2:
            csv_path = ui.ask("CSV file path", str(Path("leads.csv")))
            _run_action(
                "Previewing outreach emails...",
                lambda: leads_mod.send_outreach(csv_path=csv_path, dry_run=True),
            )
        elif choice == 3:
            csv_path = ui.ask("CSV file path", str(Path("leads.csv")))
            confirm = ui.confirm("Send real emails now?", default=False)
            if confirm:
                _run_action(
                    "Sending outreach emails...",
                    lambda: leads_mod.send_outreach(csv_path=csv_path, dry_run=False),
                )
        elif choice == 4:
            _run_action("Saving API keys...", auth.setup_api_keys)


def _automation_menu():
    from modules import scheduler

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "Automation",
            [
                "Run everything once",
                "Start the always-on scheduler",
            ],
            back_label="Back to main menu",
        )

        if choice == 0:
            return
        if choice == 1:
            shorts = _ask_int("How many Shorts?", 1)
            tweets = _ask_int("How many tweets?", 3)
            leads_enabled = ui.confirm("Also find leads?", default=False)
            _run_action(
                "Running the full autopilot flow...",
                lambda: auto.callback(shorts=shorts, tweets=tweets, find_leads=leads_enabled),
            )
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
                "Setup accounts and API keys",
                "YouTube Shorts",
                "Twitter / X",
                "Lead finder and outreach",
                "Automation",
                "Status dashboard",
            ],
            back_label="Exit CashCrab",
        )

        if choice == 0:
            ui.clear()
            return
        if choice == 1:
            _auth_menu()
        elif choice == 2:
            _youtube_menu()
        elif choice == 3:
            _twitter_menu()
        elif choice == 4:
            _leads_menu()
        elif choice == 5:
            _automation_menu()
        elif choice == 6:
            _show_status_dashboard()


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx: click.Context):
    """CashCrab - terminal money tools with a beginner-friendly menu."""
    if ctx.invoked_subcommand is None:
        _interactive_menu()


@cli.group()
def auth():
    """Manage OAuth tokens and API keys."""
    pass


@auth.command()
def youtube():
    """Link your YouTube account (OAuth2 browser flow)."""
    from modules.auth import youtube_login

    youtube_login()


@auth.command()
def twitter():
    """Link your Twitter/X account (OAuth2 PKCE browser flow)."""
    from modules.auth import twitter_login

    twitter_login()


@auth.command()
def keys():
    """Set API keys for Pexels and Google Places."""
    from modules.auth import setup_api_keys

    setup_api_keys()


@auth.command()
def status():
    """Show auth status for all services."""
    from modules.auth import status as auth_status

    auth_status()


@auth.command()
@click.argument("service", type=click.Choice(["youtube", "twitter"]))
def revoke(service):
    """Remove stored tokens for a service."""
    from modules.auth import revoke as auth_revoke

    auth_revoke(service)


@cli.group()
def yt():
    """YouTube Shorts automation."""
    pass


@yt.command()
@click.option("--topic", default=None, help="Video topic (auto-generated if empty)")
@click.option("--upload/--no-upload", default=True, help="Upload after generating")
def generate(topic, upload):
    """Generate a YouTube Short."""
    from modules import video, youtube

    result = video.generate_short(topic)

    if upload:
        youtube.upload(result["video_path"], result["title"], result["description"])


@yt.command()
def upload_all():
    """Upload all pending videos from the Shorts folder."""
    from modules import youtube

    youtube.upload_pending()


@yt.command("status")
def yt_status():
    """Show Shorts upload status."""
    from modules import youtube

    youtube.status()


@cli.group()
def tw():
    """Twitter affiliate bot."""
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


@cli.group()
def leads():
    """Local business lead finder and outreach."""
    pass


@leads.command()
@click.option("--query", default=None, help="Business type (for example: plumber)")
@click.option("--location", default=None, help="City or area to search")
@click.option("--output", default=None, help="CSV output path")
def find(query, location, output):
    """Find local businesses via Google Places."""
    from modules import leads as leads_mod

    results = leads_mod.find_leads(query, location)
    leads_mod.export_csv(results, output)


@leads.command()
@click.option("--csv", "csv_path", required=True, help="Path to leads CSV")
@click.option("--dry-run/--send", default=True, help="Preview without sending")
def outreach(csv_path, dry_run):
    """Send cold outreach emails to leads."""
    from modules import leads as leads_mod

    leads_mod.send_outreach(csv_path=csv_path, dry_run=dry_run)


@cli.command()
def schedule():
    """Run the scheduler (YouTube + Twitter on autopilot)."""
    from modules import scheduler

    scheduler.start()


@cli.command()
@click.option("--shorts", default=1, help="Number of Shorts to generate and upload")
@click.option("--tweets", default=3, help="Number of tweets to post")
@click.option("--find-leads/--no-leads", default=False, help="Also run lead finder")
def auto(shorts, tweets, find_leads):
    """Run everything once: Shorts, tweets, and optionally leads."""
    from modules import leads as leads_mod
    from modules import twitter, video, youtube

    for _ in range(shorts):
        result = video.generate_short()
        youtube.upload(result["video_path"], result["title"], result["description"])

    twitter.run_batch(tweets, affiliate_ratio=0.3)

    if find_leads:
        results = leads_mod.find_leads()
        leads_mod.export_csv(results)


@cli.command()
def dashboard():
    """Show the status dashboard."""
    _show_status_dashboard()


if __name__ == "__main__":
    cli()
