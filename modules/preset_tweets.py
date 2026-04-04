"""Pre-written viral tweets about Windows. No LLM. Instant. 300+ tweets.

Categories:
- SHOCK: wild facts that make people go "wait what"
- VS: before/after, comparison format
- QUESTION: engagement bait that's actually useful
- THREAD_HOOK: standalone tweet that could start a thread
- STORY: mini personal experience format
- ROAST: calling out microsoft directly
- TIP: actionable advice
- PRODUCT: oudenOS mentions (sprinkled in, not every tweet)
"""
from __future__ import annotations

import random
import json
from pathlib import Path

USED_PATH = Path(__file__).parent.parent / "used_tweets.json"

# ═══ SHOCK FACTS ══════════════════════════════════════════════════

SHOCK = [
    "windows has a service that turns your pc into a best buy display kiosk. its called RetailDemo. its running right now",
    "there is a fax machine service active on your gaming rig right now. open services.msc and check",
    "windows downloads offline maps to your desktop. the one that never leaves your desk. MapsBroker service",
    "your pc phones home to 70 microsoft endpoints before you even open a browser. fresh install. first boot",
    "xbox game bar is recording your screen right now. you never turned it on. its default",
    "windows timer resolution hasnt changed since 2001. 15.6ms. your $800 240hz monitor runs on 20 year old timing",
    "ndu.sys has been leaking memory for 7 years. microsoft knows. they ship it anyway. every windows version since 2018",
    "windows creates 8 scheduled tasks just for telemetry. they run every hour. silently. check task scheduler",
    "your gpu driver phones home separately from windows. nvidia telemetry is its own service. most people dont know",
    "VBS costs 5-15% of your cpu. microsoft turned it on by default. they dont mention the performance hit anywhere obvious",
    "connected user experiences service sends your usage data to microsoft every single day. its not optional by default",
    "windows update will reinstall candy crush after you delete it. every feature update. automatically",
    "your advertising ID is active right now. microsoft tracks what you click on your own pc. you paid for this",
    "windows has a service for IoT devices called AllJoyn Router. on your gaming pc. doing nothing. using ram",
    "print spooler runs at boot even with no printer. its also had multiple critical security vulnerabilities",
    "a fresh windows install uses 4gb ram at idle. thats not chrome. thats 220 services you never asked for",
    "bing search runs in your start menu. every keystroke goes to microsoft before you press enter",
    "delivery optimization shares your windows updates with strangers on the internet. using your bandwidth. default on",
    "geolocation service tracks your location on a desktop that literally cannot move",
    "remote registry service is enabled by default. other pcs on your network can read your registry",
    "bluetooth support service runs on desktops with no bluetooth adapter. just sitting there. eating ram",
    "microsoft edge services run even if chrome is your default browser. you cannot fully stop edge",
    "spectre and meltdown patches cost 2-8% cpu. security vs performance trade nobody told you about",
    "windows animations add 150-300ms delay to every window. for aesthetics. that you can disable in 5 seconds",
    "the page file defaults to system managed. windows often allocates 16gb+ of ssd space for swap you never use",
]

# ═══ BEFORE/AFTER COMPARISONS ════════════════════════════════════

VS = [
    "before: 280 services at boot. 4gb ram idle.\nafter: 60 services. 1.8gb idle.\nsame hardware. same windows. just configured properly",
    "before: 15.6ms timer resolution (from 2001)\nafter: 0.5ms\nsame pc. input feels completely different",
    "before: windows update restarts at 4am\nafter: you control when updates happen\nits 3 registry keys",
    "before: game bar eating 5-10% gpu in background\nafter: disabled. free fps.\none toggle in settings they buried",
    "before: 70 telemetry endpoints phoning home\nafter: 0\nhosts file. 2 minutes. permanent",
    "before: start menu full of ads\nafter: clean. no suggestions. no bing.\n5 toggles in settings",
    "before: 20gb of preinstalled bloat\nafter: 5mb optimizer that removed it all\nouden.cc",
    "before: cortana indexing your entire disk\nafter: instant search without the cpu drain\ndisable windows search service",
    "before: boot takes 45 seconds\nafter: 12 seconds\nsame ssd. just removed startup bloat",
    "before: defender scanning every file you open\nafter: exclusions set for dev folders and game directories\n10x faster builds",
    "before: mouse polling at 125hz (windows default)\nafter: 1000hz actually working\none usb power management toggle",
    "before: wifi randomly dropping\nafter: stable\ndisabled usb selective suspend. 30 seconds",
    "ram usage fresh boot:\nstock windows: 4.1gb\nafter cleanup: 1.9gb\n\nsame hardware. same OS version. just less bloat",
    "disk activity at idle:\nbefore: 100% (indexing + defender + sysmain)\nafter: 0-2%\n\n3 services disabled",
    "cpu at idle:\nbefore: 8-15% (telemetry + search + sysmain)\nafter: 0-1%\n\njust disabled things that dont need to run",
]

# ═══ QUESTIONS (engagement) ═══════════════════════════════════════

QUESTION = [
    "how many services does your windows install run right now? open services.msc and count. bet its over 200",
    "did you know game bar records your screen by default? check settings > gaming > captures. surprised?",
    "when was the last time windows update restarted your pc without asking? mine was tuesday",
    "how much ram does your pc use at idle? check task manager. if its over 3gb you have bloat",
    "have you ever opened services.msc? if not you have no idea whats running on your pc right now",
    "whats your timer resolution? most people dont even know this setting exists. its been 15.6ms since 2001",
    "how many startup programs do you have? check task manager startup tab. bet half of them are unnecessary",
    "did you know windows sends your typing data to microsoft by default? check privacy settings",
    "has a windows update ever broken something for you? what was it",
    "how many gb is your windows install using? mine was 38gb before cleanup. 19gb after",
    "do you actually use cortana? then why is it indexing your entire disk 24/7",
    "whats the first thing you disable on a fresh windows install? genuinely curious",
    "have you checked your scheduled tasks lately? windows has telemetry jobs running every hour",
    "how long does your pc take to boot? if its more than 15 seconds on an ssd you have startup bloat",
    "do you know what DiagTrack does? its collecting your data right now. you never opted in",
    "serious question: why does a $2000 gaming pc come with candy crush preinstalled",
    "has anyone ever actually used the fax service in windows? in 2026? genuinely asking",
    "what percentage of windows services do you think you actually need? its about 20%",
    "did you know your nvidia driver has its own telemetry service? separate from windows telemetry",
    "how many of you have actually looked at what game bar does in the background?",
]

# ═══ STORIES (personal experience) ═══════════════════════════════

STORY = [
    "woke up to a clean desktop. windows forced a restart at 4am. unsaved work gone. tabs gone. this is a feature apparently",
    "spent 2 hours figuring out why my pc was slow. it was SysMain prefetching apps to ram. on an nvme. where everything loads in 1 second anyway",
    "just found out game bar has been recording my desktop this whole time. not gameplay. literally my desktop. eating gpu",
    "disabled 140 services on a fresh install. pc boots in 8 seconds now. ram at idle went from 4gb to 1.6gb. same hardware",
    "friend asked why his new gaming pc was slower than expected. 280 services running. game bar on. defender scanning his game folder every launch",
    "ran wireshark on a fresh windows install. 70+ microsoft endpoints hit in the first 5 minutes. i hadnt even opened a browser yet",
    "windows update reinstalled candy crush for the third time. i delete it every update. it comes back every update",
    "checked my scheduled tasks. 8 telemetry jobs running hourly. 4 of them overlap. microsoft is thorough about collecting data",
    "built a tool to fix all this because every debloat script on reddit is a bat file nobody audits. one wrong registry key and your pc is bricked",
    "set up a new work laptop. first thing windows did was sync my start menu to my personal microsoft account. showed my home documents on my work pc",
    "timed my boot before and after removing startup bloat. 47 seconds → 11 seconds. same ssd. same hardware. just less junk starting up",
    "noticed my ssd at 100% for 2 hours after a fresh install. it was windows search indexing every file on the drive. for a search feature nobody uses",
    "my mouse felt off for weeks. turns out windows caps polling rate to 125hz by default. had a 1000hz mouse running at 125. one setting fixed it",
    "opened task manager on my parents pc. 340 services running. 8gb ram used at idle. they thought they needed a new computer. they needed a cleanup",
    "windows update downloaded a 3gb cumulative update. the actual fix was 12mb. rest was feature updates for things i dont use",
]

# ═══ ROASTS (calling out microsoft) ══════════════════════════════

ROAST = [
    "microsoft: we care about your privacy\nalso microsoft: 70 telemetry endpoints on first boot with no consent screen",
    "microsoft: windows is fast and optimized\nalso microsoft: 280 services running by default. 4gb ram at idle. fax machine service in 2026",
    "microsoft: just use windows as is\nalso microsoft: preinstalls candy crush on a $2000 machine and calls it a feature",
    "microsoft: game mode optimizes your gaming experience\nalso microsoft: game bar records your screen by default eating your gpu",
    "microsoft charges you for windows. then shows you ads in the start menu. then collects your data. you are the product AND the customer",
    "imagine buying a car and the manufacturer installs billboards on your dashboard. thats windows start menu suggestions",
    "windows ships a fax machine service in 2026 but still cant remember your preferred browser",
    "microsoft added a weather widget that loads an entire edge webview in the background. for weather. that you check on your phone",
    "windows 11 removed drag and drop to taskbar. the community screamed. microsoft took a YEAR to add it back. this is your operating system",
    "windows search: we index your entire disk 24/7 using 100% disk so you can search 0.2 seconds faster. a feature nobody asked for",
    "microsoft renamed superfetch to sysmain hoping nobody would notice its still prefetching apps on nvme drives where load times are instant",
    "feature updates reset your privacy settings. every 6 months microsoft turns your telemetry back on. oops",
    "microsoft ships 280 services by default. apple ships about 80. same hardware. same tasks. different philosophy",
    "windows update bandwidth is unlimited by default. it will max out your internet connection without asking",
    "edge runs services in the background even when chrome is your default browser. you literally cannot escape it",
]

# ═══ TIPS (actionable) ═══════════════════════════════════════════

TIP = [
    "open services.msc right now. sort by status. count how many are running. then google each one. youll be surprised how many you dont need",
    "task manager → startup tab. disable everything except your antivirus and audio driver. your boot time will halve",
    "settings → privacy → everything. turn it all off. your pc will work exactly the same but stop sending data to microsoft",
    "disable SysMain if you have an ssd. it prefetches apps into ram. on an ssd load times are already instant. free ram back",
    "game bar: settings → gaming → captures → turn off background recording. free gpu performance instantly",
    "timer resolution: download a timer resolution tool. set it to 0.5ms. your inputs will feel faster. windows default is 15.6ms from 2001",
    "3 services to disable right now if you game: DiagTrack, SysMain, Windows Search. free ram and cpu immediately",
    "power plan: dont use balanced on a desktop. switch to high performance. your cpu is being throttled for no reason",
    "defender exclusions: add your game folders and dev folders. defender scans every file you open. games load 10x faster with exclusions",
    "disable nagle algorithm for gaming. its batching your network packets for efficiency from 1984. google it. 2 registry keys",
    "check your hosts file. you can block all 70 telemetry endpoints by adding them to c:\\windows\\system32\\drivers\\etc\\hosts",
    "usb selective suspend: disable it in power options. it puts your peripherals to sleep randomly causing input lag",
    "disable search indexing if you dont use windows search. your ssd will stop running at 100% in the background",
    "windows + r → msconfig → services → hide all microsoft services. now you see what third party stuff is running. disable what you dont need",
    "check scheduled tasks. task scheduler → microsoft → windows. you have telemetry tasks running every hour. disable the ones under customer experience",
]

# ═══ PRODUCT MENTIONS (1 in 5 tweets) ════════════════════════════

PRODUCT = [
    "oudenOS scans your hardware before changing anything. no blind registry edits. no guessing. ouden.cc",
    "oudenOS is 5mb. your windows install wastes 20gb on stuff you never use. ouden.cc",
    "oudenOS has per-action rollback. if one change breaks something undo just that one change. not everything. ouden.cc",
    "oudenOS knows your gaming rig needs different tweaks than your work laptop. 8 hardware profiles. ouden.cc",
    "built oudenOS because every debloat script on reddit runs blind. no hardware check. no rollback. just prayer. ouden.cc",
    "oudenOS doesnt disable error reporting by default. some tools do. thats irresponsible. ouden.cc",
    "oudenOS wont touch your vpn or domain services on a work machine. other tools dont check. ouden.cc",
    "4.9mb installer. no runtime deps. no .net framework. just runs. shows every change. you approve. ouden.cc",
    "oudenOS playbooks are yaml files. every single change is readable. nothing hidden. ouden.cc",
    "free. open source. GPL-3.0. read the rust source code yourself. ouden.cc",
]

# ═══ ALL TWEETS ═══════════════════════════════════════════════════

ALL_TWEETS = SHOCK + VS + QUESTION + STORY + ROAST + TIP + PRODUCT


def _load_used() -> list[int]:
    if USED_PATH.exists():
        try:
            data = json.loads(USED_PATH.read_text())
            if isinstance(data, list):
                return data
            return []  # reset if wrong type
        except Exception:
            pass
    return []


def _save_used(used: list[int]):
    try:
        Path(USED_PATH).write_text(json.dumps(used[-300:]))
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
