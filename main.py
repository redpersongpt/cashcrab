#!/usr/bin/env python3
import click


@click.group()
def cli():
    """MoneyTools - Automated income toolkit."""
    pass


# ── Auth ─────────────────────────────────────────────

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
    """Set API keys for Pexels, Google Places."""
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


# ── YouTube ──────────────────────────────────────────

@cli.group()
def yt():
    """YouTube Shorts automation."""
    pass


@yt.command()
@click.option("--topic", default=None, help="Video topic (auto-generated if empty)")
@click.option("--upload/--no-upload", default=True, help="Upload after generating")
def generate(topic, upload):
    """Generate a YouTube Short (script -> audio -> video -> upload)."""
    from modules import video, youtube

    result = video.generate_short(topic)
    click.echo(f"\nVideo ready: {result['video_path']}")
    click.echo(f"Title: {result['title']}")

    if upload:
        youtube.upload(result["video_path"], result["title"], result["description"])


@yt.command()
def upload_all():
    """Upload all pending videos from shorts/ folder."""
    from modules import youtube
    youtube.upload_pending()


@yt.command("status")
def yt_status():
    """Show upload status."""
    from modules import youtube
    youtube.status()


# ── Twitter ──────────────────────────────────────────

@cli.group()
def tw():
    """Twitter affiliate bot."""
    pass


@tw.command()
@click.option("--count", default=1, help="Number of tweets")
@click.option("--affiliate-ratio", default=0.3, help="Ratio of affiliate vs organic tweets")
def post(count, affiliate_ratio):
    """Post tweet(s) - mix of affiliate and organic."""
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


# ── Leads ────────────────────────────────────────────

@cli.group()
def leads():
    """Local business lead finder & outreach."""
    pass


@leads.command()
@click.option("--query", default=None, help="Business type (e.g. plumber)")
@click.option("--location", default=None, help="City/area to search")
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


# ── Scheduler ────────────────────────────────────────

@cli.command()
def schedule():
    """Run the scheduler (YouTube + Twitter on autopilot)."""
    from modules import scheduler
    scheduler.start()


# ── Pipeline (full auto) ────────────────────────────

@cli.command()
@click.option("--shorts", default=1, help="Number of shorts to generate & upload")
@click.option("--tweets", default=3, help="Number of tweets to post")
@click.option("--find-leads/--no-leads", default=False, help="Also run lead finder")
def auto(shorts, tweets, find_leads):
    """Run everything once: generate shorts, post tweets, find leads."""
    from modules import video, youtube, twitter

    click.echo("=== YouTube Shorts ===")
    for i in range(shorts):
        click.echo(f"\n[{i+1}/{shorts}]")
        try:
            result = video.generate_short()
            youtube.upload(result["video_path"], result["title"], result["description"])
        except Exception as e:
            click.echo(f"  Failed: {e}")

    click.echo("\n=== Twitter ===")
    twitter.run_batch(tweets, affiliate_ratio=0.3)

    if find_leads:
        click.echo("\n=== Lead Finder ===")
        from modules import leads as leads_mod
        results = leads_mod.find_leads()
        leads_mod.export_csv(results)

    click.echo("\nDone.")


if __name__ == "__main__":
    cli()
