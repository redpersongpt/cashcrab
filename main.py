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
                "Connect TikTok",
                "Connect Instagram",
                "Save keys and webhooks",
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
            from modules import tiktok

            _run_action("Connecting TikTok...", tiktok.login)
        elif choice == 4:
            from modules import instagram

            _run_action("Connecting Instagram...", instagram.login)
        elif choice == 5:
            _run_action("Saving API keys...", auth.setup_api_keys)
        elif choice == 6:
            _run_action("Loading status...", auth.status)
        elif choice == 7:
            service_choice = None

            def revoke_prompt():
                nonlocal service_choice
                local_ui = _ui()
                service_choice = local_ui.menu(
                    "Which saved login should be removed?",
                    ["YouTube", "Twitter / X", "TikTok", "Instagram"],
                    back_label="Cancel",
                )
                if service_choice == 1:
                    auth.revoke("youtube")
                elif service_choice == 2:
                    auth.revoke("twitter")
                elif service_choice == 3:
                    auth.revoke("tiktok")
                elif service_choice == 4:
                    auth.revoke("instagram")

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
            crosspost_tiktok = ui.confirm("Also cross-post to TikTok if configured?", default=False)
            crosspost_instagram = ui.confirm("Also cross-post to Instagram if configured?", default=False)

            def generate_and_upload():
                from modules import crosspost

                result = video.generate_short(topic)
                youtube.upload(result["video_path"], result["title"], result["description"])
                crosspost.publish_short(
                    result["video_path"],
                    result["title"],
                    result["description"],
                    tiktok_enabled=crosspost_tiktok,
                    instagram_enabled=crosspost_instagram,
                )

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


def _tiktok_menu():
    from modules import tiktok

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "TikTok",
            [
                "Upload a specific MP4",
                "Upload the newest Short",
                "Connect TikTok",
            ],
            back_label="Back to main menu",
        )

        if choice == 0:
            return
        if choice == 1:
            file_path = ui.ask("MP4 file path")
            title = ui.ask_or_skip("Title") or Path(file_path).stem.replace("_", " ").replace("-", " ").title()
            _run_action("Uploading to TikTok...", lambda: tiktok.upload(file_path, title))
        elif choice == 2:
            title = ui.ask_or_skip("Title")
            _run_action("Uploading the newest Short to TikTok...", lambda: tiktok.upload_latest(title=title))
        elif choice == 3:
            _run_action("Connecting TikTok...", tiktok.login)


def _instagram_menu():
    from modules import instagram

    ui = _ui()

    while True:
        ui.clear()
        ui.banner()
        choice = ui.menu(
            "Instagram Reels",
            [
                "Upload a specific MP4 as a Reel",
                "Upload the newest Short as a Reel",
                "Connect Instagram",
            ],
            back_label="Back to main menu",
        )

        if choice == 0:
            return
        if choice == 1:
            file_path = ui.ask("MP4 file path")
            caption = ui.ask_or_skip("Caption") or Path(file_path).stem.replace("_", " ").replace("-", " ")
            public_url = ui.ask_or_skip("Public video URL")
            _run_action(
                "Publishing to Instagram Reels...",
                lambda: instagram.upload(file_path, caption=caption, public_url=public_url),
            )
        elif choice == 2:
            caption = ui.ask("Caption")
            public_url = ui.ask_or_skip("Public video URL")
            _run_action(
                "Publishing the newest Short to Instagram Reels...",
                lambda: instagram.upload_latest(caption=caption, public_url=public_url),
            )
        elif choice == 3:
            _run_action("Connecting Instagram...", instagram.login)


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
            crosspost_tiktok = ui.confirm("Also cross-post Shorts to TikTok?", default=False)
            crosspost_instagram = ui.confirm("Also cross-post Shorts to Instagram?", default=False)
            _run_action(
                "Running the full autopilot flow...",
                lambda: auto.callback(
                    shorts=shorts,
                    tweets=tweets,
                    find_leads=leads_enabled,
                    crosspost_tiktok=crosspost_tiktok,
                    crosspost_instagram=crosspost_instagram,
                ),
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
                "TikTok",
                "Instagram Reels",
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
            _tiktok_menu()
        elif choice == 5:
            _instagram_menu()
        elif choice == 6:
            _leads_menu()
        elif choice == 7:
            _automation_menu()
        elif choice == 8:
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
def tiktok():
    """Link your TikTok account."""
    from modules import tiktok

    tiktok.login()


@auth.command()
def instagram():
    """Link your Instagram / Meta account."""
    from modules import instagram

    instagram.login()


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
@click.argument("service", type=click.Choice(["youtube", "twitter", "tiktok", "instagram"]))
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
@click.option("--crosspost-tiktok/--no-crosspost-tiktok", default=None, help="Also cross-post to TikTok")
@click.option("--crosspost-instagram/--no-crosspost-instagram", default=None, help="Also cross-post to Instagram")
@click.option("--instagram-public-url", default=None, help="Public MP4 URL for Instagram publishing")
def generate(topic, upload, crosspost_tiktok, crosspost_instagram, instagram_public_url):
    """Generate a YouTube Short."""
    from modules import crosspost, video, youtube

    result = video.generate_short(topic)

    if upload:
        youtube.upload(result["video_path"], result["title"], result["description"])
        crosspost.publish_short(
            result["video_path"],
            result["title"],
            result["description"],
            tiktok_enabled=crosspost_tiktok,
            instagram_enabled=crosspost_instagram,
            instagram_public_url=instagram_public_url,
        )


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
def tt():
    """TikTok uploads."""
    pass


@tt.command()
@click.argument("file_path")
@click.option("--title", required=True, help="TikTok caption/title")
def upload(file_path, title):
    """Upload a specific MP4 to TikTok."""
    from modules import tiktok

    tiktok.upload(file_path, title)


@tt.command("upload-latest")
@click.option("--title", default=None, help="Optional title override")
def tt_upload_latest(title):
    """Upload the newest generated Short to TikTok."""
    from modules import tiktok

    tiktok.upload_latest(title=title)


@cli.group()
def ig():
    """Instagram Reels publishing."""
    pass


@ig.command("upload")
@click.argument("file_path")
@click.option("--caption", required=True, help="Instagram caption")
@click.option("--public-url", default=None, help="Public MP4 URL for Meta to fetch")
def upload_reel(file_path, caption, public_url):
    """Publish a specific MP4 as an Instagram Reel."""
    from modules import instagram

    instagram.upload(file_path, caption=caption, public_url=public_url)


@ig.command("upload-latest")
@click.option("--caption", required=True, help="Instagram caption")
@click.option("--public-url", default=None, help="Public MP4 URL for Meta to fetch")
def ig_upload_latest(caption, public_url):
    """Publish the newest generated Short as an Instagram Reel."""
    from modules import instagram

    instagram.upload_latest(caption=caption, public_url=public_url)


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


@leads.command("campaign-update")
@click.argument("campaign_id")
@click.option("--opened", type=int, default=None, help="Set opened count")
@click.option("--replied", type=int, default=None, help="Set replied count")
def campaign_update(campaign_id, opened, replied):
    """Update lead campaign open/reply counts for analytics."""
    from modules import analytics

    analytics.update_lead_campaign(campaign_id, opened=opened, replied=replied)
    click.echo(f"Updated campaign: {campaign_id}")


@cli.command()
def schedule():
    """Run the scheduler (YouTube + Twitter on autopilot)."""
    from modules import scheduler

    scheduler.start()


@cli.command()
@click.option("--shorts", default=1, help="Number of Shorts to generate and upload")
@click.option("--tweets", default=3, help="Number of tweets to post")
@click.option("--find-leads/--no-leads", default=False, help="Also run lead finder")
@click.option("--crosspost-tiktok/--no-crosspost-tiktok", default=None, help="Also cross-post Shorts to TikTok")
@click.option("--crosspost-instagram/--no-crosspost-instagram", default=None, help="Also cross-post Shorts to Instagram")
def auto(shorts, tweets, find_leads, crosspost_tiktok, crosspost_instagram):
    """Run everything once: Shorts, tweets, and optionally leads."""
    from modules import leads as leads_mod
    from modules import crosspost, twitter, video, youtube

    for _ in range(shorts):
        result = video.generate_short()
        youtube.upload(result["video_path"], result["title"], result["description"])
        crosspost.publish_short(
            result["video_path"],
            result["title"],
            result["description"],
            tiktok_enabled=crosspost_tiktok,
            instagram_enabled=crosspost_instagram,
        )

    twitter.run_batch(tweets, affiliate_ratio=0.3)

    if find_leads:
        results = leads_mod.find_leads()
        leads_mod.export_csv(results)


@cli.command()
@click.option("--export", "export_path", default=None, help="Optional CSV export path")
def dashboard(export_path):
    """Show the status dashboard."""
    from modules import analytics, auth, youtube

    if export_path:
        path = analytics.export_csv(export_path)
        click.echo(f"Exported analytics to {path}")

    auth.status()
    youtube.status()
    analytics.dashboard()


if __name__ == "__main__":
    cli()
