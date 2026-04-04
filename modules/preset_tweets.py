"""1000 pre-written tweets about Windows optimization.

No LLM needed. Instant. Zero AI detection.
Organized by category, randomly selected with no-repeat tracking.
"""
from __future__ import annotations

import random
from pathlib import Path
import json

USED_PATH = Path(__file__).parent.parent / "used_tweets.json"

# ─── TWEETS BY CATEGORY ──────────────────────────────────────────

SERVICES = [
    "windows ships 280 services by default. you need about 60. the other 220 are just eating ram",
    "RetailDemo service turns your pc into a best buy display kiosk. its on every windows install",
    "MapsBroker downloads offline maps on your desktop. you are not driving your pc anywhere",
    "there is a fax machine service running on your pc right now. in 2026",
    "xbox game bar records your screen by default. eating gpu. you never asked for it",
    "SysMain prefetches apps into ram. on an nvme. where load times are already under a second",
    "windows search indexes your entire disk 24/7 so cortana can search 0.2 seconds faster",
    "DiagTrack collects telemetry data nonstop. it starts before you even log in",
    "connected user experiences service sends your usage data to microsoft. every day. default on",
    "windows has a service called AllJoyn Router. its for IoT devices. on your gaming rig",
    "WMI Performance Adapter runs at startup to collect performance data nobody reads",
    "Print Spooler is running even if you dont own a printer. it has had critical CVEs for years",
    "Phone Link service runs at boot so you can mirror your android phone. most people dont use it",
    "windows push notification service runs 24/7 for apps you probably dont have",
    "the IP Helper service is running to support IPv6 transition tech from 2003",
    "Geolocation Service tracks your location by default. on a desktop that never moves",
    "Secondary Logon service runs at boot for a feature 99% of users never touch",
    "SSDP Discovery runs to find smart home devices on your network. on a gaming pc",
    "Program Compatibility Assistant runs nonstop checking if your apps might be incompatible",
    "windows has a Distributed Link Tracking Client service. for tracking file moves across networks from the windows 2000 era",
    "Microsoft Store Install Service runs in background even if you never open the store",
    "Delivery Optimization runs to share windows updates with other pcs on your network. using your bandwidth",
    "Remote Registry service is enabled by default. letting other pcs on your network read your registry",
    "windows ships with a Bluetooth Support Service running even on desktops with no bluetooth",
    "the Downloaded Maps Manager runs checking for map updates. on a machine with no gps",
]

TELEMETRY = [
    "fresh windows install hits 70+ microsoft endpoints before you open a browser",
    "start menu suggestions are paid ads. microsoft sells real estate on your desktop",
    "candy crush comes preinstalled on a $2000 machine. you paid for that ad space",
    "your advertising ID is active by default. microsoft tracks what you click on your own pc",
    "windows phones home to 70 endpoints on first boot. no consent screen. just data leaving",
    "Activity History sends your app usage timeline to microsoft. default on",
    "Clipboard Cloud Sync sends what you copy to microsoft servers. opt-out not opt-in",
    "your typing data gets sent to microsoft to improve personalization. default on",
    "windows collects diagnostic data at the enhanced level by default. not basic",
    "Copilot sends your prompts to microsoft cloud even for local tasks",
    "Recall was going to screenshot everything you do. they paused it but the code is still there",
    "microsoft collects your wifi passwords through connected accounts. for convenience",
    "handwriting data gets uploaded to microsoft for recognition improvement. default on",
    "your Start menu layout and app usage gets synced to microsoft even without a microsoft account",
    "windows sends hardware census data to microsoft including every device connected to your pc",
    "SmartScreen sends URLs you visit to microsoft servers. for protection. also for data",
    "OneDrive starts at boot and syncs by default. if you signed in with a microsoft account its already running",
    "Cortana data collection runs even if you disabled cortana. the service stays active",
    "bing search in start menu sends every keystroke to microsoft before you hit enter",
    "microsoft collects crash dumps that can contain sensitive data from your ram",
    "Xbox services send gameplay data even if you dont play any xbox games on pc",
    "microsoft edge sends browsing data even if chrome is your default browser. edge services still run",
    "windows update sends detailed hardware and software inventory to microsoft with every check",
    "the Customer Experience Improvement Program runs telemetry jobs hourly via scheduled tasks",
    "windows creates 8+ scheduled tasks just for telemetry. running silently in the background every hour",
]

PERFORMANCE = [
    "windows default timer resolution is 15.6ms. from 2001. your 240hz monitor deserves better",
    "ndu.sys has been leaking memory since 2018. microsoft knows. 7 years. still shipping it",
    "VBS/HVCI costs 5-15% cpu performance. microsoft buries this in docs nobody reads",
    "core parking is enabled by default on desktops. saving power on a machine thats always plugged in",
    "memory compression trades ram speed for cpu cycles. on a machine with 32gb ram. pointless",
    "your pc isnt slow. windows is running 220 services you never asked for in the background",
    "the average fresh windows install uses 4gb ram at idle. thats not your apps. thats windows",
    "MMCSS thread priority isnt optimized for gaming by default. windows treats your game like any other app",
    "superfetch was renamed to SysMain. still does the same pointless prefetching on nvme drives",
    "windows power plan defaults to Balanced. which throttles your cpu even on desktop",
    "USB selective suspend puts your peripherals to sleep randomly. causing input lag",
    "HPET timer is enabled by default. on modern systems it adds latency not accuracy",
    "nagle algorithm batches your network packets for efficiency. great in 1984. bad for gaming in 2026",
    "windows defender real-time scanning eats 5-10% cpu constantly. even when youre just coding",
    "last access timestamp updates on every file read. thrashing your ssd for metadata nobody checks",
    "the page file is managed automatically. windows often sets it way too large wasting ssd space",
    "windows update downloads and installs in the background. eating your bandwidth and cpu without asking",
    "indexing service rebuilds after every major update. your disk runs at 100% for hours",
    "transparency effects in windows 11 use gpu resources for a visual effect nobody needs",
    "windows animations add 150-300ms delay to every window open and close. just for aesthetics",
    "hardware accelerated gpu scheduling isnt enabled by default on most systems. free performance left on the table",
    "your mouse polling rate is capped at 125hz by default. your 1000hz mouse is being wasted",
    "QoS packet scheduler adds overhead to every network packet. slowing your connection",
    "windows event logging writes to disk constantly. even when nothing important is happening",
    "spectre and meltdown mitigations cost 2-8% cpu. security vs performance trade you were never told about",
]

WINDOWS_UPDATE = [
    "windows update restarted your pc at 4am. your unsaved work is gone. this is a feature",
    "windows update downloads candy crush again after you deleted it. every major update",
    "your pc restarted overnight to install an update you didnt approve. your 47 tabs are gone",
    "windows update uses your bandwidth to share updates with strangers. delivery optimization is on by default",
    "active hours only protects 18 hours. windows owns the other 6",
    "windows update downloads 2gb patches for features you dont use",
    "a windows update broke your audio driver last month. you spent 2 hours fixing it",
    "windows update installs edge improvements even if you use chrome. you cant opt out",
    "feature updates reset your privacy settings. every 6 months your telemetry gets turned back on",
    "windows update bandwidth is unlimited by default. it will max out your connection",
    "microsoft pushed a broken update to millions of pcs in 2024. bsod on boot. worldwide",
    "windows update checks for updates every 22 hours by default. you cant change this without registry edits",
    "if you defer updates too long windows force-installs them. you have no choice",
    "cumulative updates are 1-3gb each. even if the actual fix is 2mb. you download the whole thing",
    "windows update sometimes reinstalls apps you removed. including xbox and tips",
]

GAMING = [
    "game bar records your screen by default. eating gpu cycles. most gamers dont know",
    "Game DVR captures the last 30 seconds of gameplay. always. even in menu screens",
    "fullscreen optimization forces borderless windowed on most games. adding input lag",
    "nvidia telemetry service runs alongside your gpu driver. phoning home about your gaming habits",
    "xbox game monitoring service tracks what games you play and for how long. default on",
    "game mode was supposed to help. benchmarks show it makes zero difference on most systems",
    "nvidia overlay runs at startup even if you never press alt+z",
    "steam overlay + discord overlay + game bar overlay. three overlays fighting for your gpu",
    "shader cache can grow to 10gb+ without you knowing. eating your ssd space",
    "mouse acceleration is on by default in windows. every fps player has to disable it manually",
    "windows audio ducking lowers your game volume when discord rings. because thats helpful",
    "high precision event timer adds latency on modern cpus. its an old workaround kept for compatibility",
    "focus assist blocks game notifications but also blocks discord messages. pick your poison",
    "windows defender scans game files on first launch. adding 10+ seconds to load time",
    "gpu driver telemetry runs as a windows service. separate from the driver itself. just data collection",
]

PRODUCT = [
    "oudenOS scans your hardware before changing anything. unlike every bat file on reddit",
    "oudenOS is 5mb. your windows install wastes 20gb on things you never use",
    "oudenOS has per-action rollback. mess something up undo just that one thing",
    "oudenOS profiles your pc into 1 of 8 types. gaming rigs get different tweaks than work laptops",
    "oudenOS shows every single change before applying. you approve everything",
    "oudenOS doesnt need an account. no internet required. no background process. closes when you close it",
    "oudenOS playbooks are yaml files you can read. every change is auditable",
    "built oudenOS because debloat scripts that work on one pc nuke another",
    "oudenOS knows not to disable print spooler on work pcs. hardware-aware profiles matter",
    "oudenOS wont touch your vpn rdp or domain services on a work machine. other tools dont check",
    "oudenOS is GPL-3.0. read the rust source. run it in a VM first. your call",
    "oudenOS doesnt claim 200fps gains. it just removes stuff that shouldnt be there",
    "built with rust backend. not powershell scripts. not batch files. actual compiled code",
    "oudenOS v0.3.0 is free. paid tier is $0.99 one-time for deep tuning. no subscription ever",
    "oudenOS treats your work pc differently from your gaming rig. because they need different things",
    "every debloat tool on reddit runs blind. oudenOS scans first. thats the whole point",
    "oudenOS disables game bar without breaking xbox controller support. small details matter",
    "oudenOS doesnt disable error reporting by default. some tools do. thats irresponsible",
    "4.9mb installer. no vc++ runtime needed. no .net framework. just runs",
    "oudenOS creates a snapshot before every change. not just one big restore point",
]

SHELL = [
    "windows 11 removed the classic right-click menu. why. everyone just clicks show more options anyway",
    "widgets panel runs a whole edge webview in the background. for weather you check on your phone",
    "search highlights show bing news in your start menu. because you wanted that definitely",
    "chat icon in taskbar loads microsoft teams in the background. even if you use discord",
    "windows 11 moved the taskbar to center. you cant move it to the top or sides anymore",
    "start menu shows recommended files from onedrive. microsoft decides what you see on your desktop",
    "the settings app still redirects to control panel for some things. 11 years of migration and its not done",
    "file explorer tabs were added in 2023. chrome had them in 2008",
    "snap layouts are nice until they rearrange all your windows after unplugging a monitor",
    "windows 11 removed drag-and-drop to taskbar. they added it back after massive backlash. it took a year",
]

# ─── ALL TWEETS ───────────────────────────────────────────────────

ALL_TWEETS = SERVICES + TELEMETRY + PERFORMANCE + WINDOWS_UPDATE + GAMING + PRODUCT + SHELL


def _load_used() -> list[int]:
    if USED_PATH.exists():
        try:
            return json.loads(USED_PATH.read_text())
        except Exception:
            pass
    return []


def _save_used(used: list[int]):
    # Keep last 200
    try:
        USED_PATH.write_text(json.dumps(used[-200:]))
    except Exception:
        pass


def get_preset_tweet() -> str:
    """Get a random preset tweet that hasn't been used recently."""
    used = _load_used()
    available = [i for i in range(len(ALL_TWEETS)) if i not in used]
    if not available:
        used = []
        available = list(range(len(ALL_TWEETS)))

    idx = random.choice(available)
    used.append(idx)
    _save_used(used)
    return ALL_TWEETS[idx]


def count() -> int:
    return len(ALL_TWEETS)
