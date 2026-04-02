import csv
import re
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from modules.config import section, ROOT
from modules.auth import get_api_key
from modules import ui

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _places_search(query: str, location: str, radius: int, api_key: str) -> list[dict]:
    geocode_resp = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": location, "key": api_key},
        timeout=10,
    )
    geocode_resp.raise_for_status()
    results = geocode_resp.json().get("results", [])
    if not results:
        ui.warn(f"Could not locate: {location}")
        return []

    loc = results[0]["geometry"]["location"]
    lat, lng = loc["lat"], loc["lng"]

    places_resp = requests.get(
        "https://maps.googleapis.com/maps/api/place/textsearch/json",
        params={
            "query": f"{query} near {location}",
            "location": f"{lat},{lng}",
            "radius": radius,
            "key": api_key,
        },
        timeout=10,
    )
    places_resp.raise_for_status()

    businesses = []
    for place in places_resp.json().get("results", []):
        place_id = place["place_id"]
        detail = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={
                "place_id": place_id,
                "fields": "name,formatted_phone_number,website,formatted_address,rating,user_ratings_total",
                "key": api_key,
            },
            timeout=10,
        ).json().get("result", {})

        businesses.append({
            "name": detail.get("name", place.get("name", "")),
            "address": detail.get("formatted_address", ""),
            "phone": detail.get("formatted_phone_number", ""),
            "website": detail.get("website", ""),
            "rating": detail.get("rating", ""),
            "reviews": detail.get("user_ratings_total", ""),
            "email": "",
        })
        time.sleep(0.2)

    return businesses


def _extract_email(website: str, filters: list[str]) -> str:
    if not website:
        return ""

    try:
        resp = requests.get(website, timeout=8, headers={
            "User-Agent": "Mozilla/5.0 (compatible; LeadBot/1.0)"
        })
        emails = EMAIL_RE.findall(resp.text)

        for email in emails:
            local = email.split("@")[0].lower()
            if not any(f in local for f in filters):
                if not email.endswith((".png", ".jpg", ".gif", ".svg")):
                    return email
    except Exception:
        pass

    return ""


def find_leads(query: str | None = None, location: str | None = None) -> list[dict]:
    cfg = section("leads")
    api_key = get_api_key("google_places") or cfg.get("google_places_api_key", "")
    if not api_key:
        raise RuntimeError("No Google Places API key. Open CashCrab -> Setup -> Save API keys.")
    queries = [query] if query else cfg.get("search_queries", [])
    locations = [location] if location else cfg.get("locations", [])
    filters = cfg.get("email_filter", ["noreply", "no-reply", "donotreply"])

    all_leads = []

    for q in queries:
        for loc in locations:
            ui.info(f"Searching for {q} in {loc}...")
            businesses = _places_search(q, loc, cfg.get("radius_meters", 5000), api_key)
            ui.info(f"Found {len(businesses)} businesses")

            for biz in businesses:
                biz["email"] = _extract_email(biz["website"], filters)
                if biz["email"]:
                    ui.info(f"{biz['name']}: {biz['email']}")
                biz["query"] = q
                biz["location"] = loc

            with_email = sum(1 for biz in businesses if biz.get("email"))
            try:
                from modules import analytics, notify

                analytics.track_lead_search(query=q, location=loc, total=len(businesses), with_email=with_email)
                notify.leads_found(query=q, location=loc, count=len(businesses), with_email=with_email)
            except Exception:
                pass

            all_leads.extend(businesses)

    return all_leads


def export_csv(leads: list[dict], output_path: str | None = None) -> str:
    if not leads:
        ui.warn("No leads found, so nothing was exported.")
        return ""

    cfg = section("leads")
    if not output_path:
        output_path = str(ROOT / "leads.csv")

    fields = ["name", "address", "phone", "website", "email",
              "rating", "reviews", "query", "location"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)

    with_email = sum(1 for l in leads if l.get("email"))
    ui.success(f"Saved {len(leads)} leads ({with_email} with email) to {output_path}")
    return output_path


def send_outreach(leads: list[dict] | None = None, csv_path: str | None = None,
                  dry_run: bool = False):
    cfg = section("leads")
    smtp_cfg = cfg["smtp"]
    template = cfg["email_template"]
    from_name = cfg.get("from_name", "")
    physical = cfg.get("physical_address", "")

    if csv_path:
        with open(csv_path, newline="", encoding="utf-8") as f:
            leads = list(csv.DictReader(f))

    if not leads:
        ui.warn("No leads were provided.")
        return

    emailable = [l for l in leads if l.get("email")]
    seen = set()
    unique = []
    for l in emailable:
        if l["email"] not in seen:
            seen.add(l["email"])
            unique.append(l)

    ui.info(f"{len(unique)} unique emails to send (from {len(leads)} leads)")

    if dry_run:
        for l in unique[:5]:
            subject = template["subject"].format(
                business_name=l["name"], from_name=from_name
            )
            ui.info(f"Preview -> {l['email']} | {subject}")
        if len(unique) > 5:
            ui.info(f"... and {len(unique) - 5} more")
        return

    server = smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"])
    try:
        server.starttls()
        server.login(smtp_cfg["email"], smtp_cfg["password"])

        sent = 0
        campaign_id = f"{Path(csv_path).stem if csv_path else 'manual'}-{int(time.time())}"
        for l in unique:
            subject = template["subject"].format(
                business_name=l["name"], from_name=from_name
            )
            body = template["body"].format(
                business_name=l["name"],
                from_name=from_name,
                physical_address=physical,
            )

            msg = MIMEMultipart()
            msg["From"] = f"{from_name} <{smtp_cfg['email']}>"
            msg["To"] = l["email"]
            msg["Subject"] = subject
            msg["List-Unsubscribe"] = f"<mailto:{smtp_cfg['email']}?subject=STOP>"
            msg.attach(MIMEText(body, "plain"))

            try:
                server.sendmail(smtp_cfg["email"], l["email"], msg.as_string())
                sent += 1
                ui.success(f"Sent to {l['name']} ({l['email']})")
                time.sleep(3)
            except Exception as e:
                ui.fail(f"Could not send to {l['email']}: {e}")

        ui.success(f"Finished. Sent {sent} of {len(unique)} emails.")
        try:
            from modules import analytics

            analytics.track_lead_campaign(
                campaign_id=campaign_id,
                source=csv_path or "manual",
                sent=sent,
            )
            ui.info(f"Campaign tracked as: {campaign_id}")
        except Exception:
            pass
    finally:
        server.quit()
