"""150 pre-written replies for engagement tweets.

These are NOT LLM-generated at runtime — they're handwritten templates
that get matched to tweet patterns. Zero AI detection risk.

Pattern types:
- "why does everyone use X" → Windows defense angle
- "what's your favorite tool/language/setup" → practical answer + windows mention
- "be honest / unpopular opinion" → hot take about Windows/PCs
- "MacBook vs" → balanced take leaning Windows
- "what are you working on" → mention building oudenOS
- "dev setup / workspace" → PC setup angle
"""
from __future__ import annotations

import random
from datetime import datetime

# ─── Pattern matchers ─────────────────────────────────────────────

PATTERNS = {
    "why_macbook": [
        "macbook", "everyone using mac", "why mac", "macbook pro",
        "all devs use mac", "everyone has a mac",
    ],
    "favorite_tool": [
        "favorite tool", "what tool do you", "best tool",
        "what do you use for", "recommend a tool", "tool you cant live without",
    ],
    "favorite_language": [
        "favorite language", "best language", "what language",
        "which language", "language you love", "language you hate",
        "favorite programming", "whats your language", "programming language",
    ],
    "setup_workspace": [
        "your setup", "show your setup", "dev setup", "workspace",
        "your desk", "wfh setup", "what monitor", "what keyboard",
    ],
    "be_honest": [
        "be honest", "unpopular opinion", "hot take", "controversial",
        "confession", "am i the only", "anyone else",
    ],
    "working_on": [
        "what are you working on", "building anything", "side project",
        "what are you building", "ship anything", "working on something",
    ],
    "windows_vs": [
        "windows vs", "linux vs windows", "mac vs windows", "mac vs pc",
        "switch to linux", "switch to mac", "left windows",
    ],
    "dev_life": [
        "dev life", "programmer life", "coding at", "debugging",
        "git commit", "production bug", "deploy friday",
    ],
    "pc_hardware": [
        "new pc", "built a pc", "pc build", "gpu", "what specs",
        "how much ram", "upgrade", "new laptop", "which laptop",
    ],
    "morning_routine": [
        "morning routine", "first thing you do", "start your day",
        "morning dev", "coffee and code",
    ],
}

# ─── Reply pools (150 total) ─────────────────────────────────────

REPLIES = {
    "why_macbook": [
        "because most people havent configured windows properly. once you kill the 220 useless services its a different machine",
        "unix terminal is nice but WSL exists and my pc cost half the price for double the specs",
        "battery life and trackpad are legit good. but for raw performance per dollar windows pcs still win",
        "peer pressure mostly. windows with proper optimization runs circles around base macOS for dev work",
        "the terminal argument died when WSL2 came out. now its just brand preference",
        "real answer: most people never optimize their windows install so it feels slow. fix that and its great",
        "macbook is solid hardware. windows is solid software when configured right. people just dont configure it",
        "hot take: windows devs who optimize their system are more productive than macbook devs who dont",
        "because nobody teaches you how to properly set up windows. so people default to mac",
        "i mass on thanksgiving and run 280 services by default on windows but still prefer it over mac. fight me",
        "macbook for the vibes. pc for the performance. both valid",
        "honest answer: macbook is great out of the box. windows is greater once you spend 10 minutes optimizing it",
        "been on both. windows with debloat + wsl is my endgame setup",
        "macbook hardware is elite. windows software flexibility is elite. pick your priority",
        "because people dont know windows ships with a fax machine service in 2026 and think the OS itself is slow",
    ],

    "favorite_tool": [
        "vscode for everything. tried every editor, always came back",
        "wezterm + neovim. once you go terminal you dont go back",
        "docker. i mass on thanksgiving and cant work without containers anymore",
        "honestly github copilot. saves me hours on boilerplate",
        "windows terminal + pwsh. underrated combo",
        "notion for docs, linear for tasks, vscode for code. thats the stack",
        "ffmpeg. does everything and nobody understands it",
        "just built oudenOS actually. 5mb windows optimizer. scratched my own itch",
        "git. boring answer but its the tool that saved me the most hours",
        "task manager. seriously. half of debugging windows is just reading services tab",
        "bruno for API testing. postman got too bloated",
        "everything from sysinternals. process monitor is magic",
        "turborepo. monorepos without the pain",
        "gh cli. never opening github in browser again",
        "wireshark. you havent debugged until youve watched packets",
    ],

    "favorite_language": [
        "typescript. javascript but it respects you",
        "rust. borrow checker is pain but the memory safety is worth it",
        "python for scripts, typescript for apps, rust for performance. no single answer",
        "go. simple, fast, boring in the best way",
        "whatever ships the product. language wars are a waste of time",
        "rust changed how i think about memory. even when i write typescript now",
        "python. not the fastest but the fastest to ship with",
        "c. because sometimes you need to talk directly to the hardware",
        "typescript. the jump from js to ts is the best ROI in programming",
        "honestly sql. most underrated language. been around 50 years and still everywhere",
        "rust for backends, typescript for frontends, python for scripts. the holy trinity",
        "whichever one pays the bills this month",
        "lua. embed it in anything and it just works",
        "swift. apple got the developer experience right",
        "bash. ugly but it runs the world",
    ],

    "setup_workspace": [
        "dual monitor, mechanical keyboard, standing desk. basic but it works",
        "one ultrawide > two monitors. less neck movement",
        "custom pc, 32gb ram, nvme. debloated windows. runs like a dream",
        "minimalist. laptop, external monitor, good chair. nothing else",
        "the chair matters more than the monitor. your back will thank you later",
        "dark mode everything. flux for night. blue light glasses are a scam though",
        "vertical monitor for code, horizontal for browser. game changer",
        "same desk for 5 years. upgraded the chair twice. priorities",
        "no rgb. just good airflow and quiet fans. i mass on thanksgiving and want silence",
        "home office > coworking > office. in that order. permanently",
        "split keyboard changed my life. wrist pain gone in 2 weeks",
        "biggest upgrade wasnt hardware. it was debloating windows and getting 8gb ram back",
        "3 monitors sounds cool until you realize you only look at one",
        "good mic > good camera for remote work. nobody cares what you look like",
        "invested in the chair first. everything else is secondary to your spine",
    ],

    "be_honest": [
        "most people dont need kubernetes. a single server handles more traffic than you think",
        "your side project doesnt need microservices. a monolith is fine",
        "half of senior devs are just good at googling. and thats ok",
        "code reviews are more about ego than quality 90% of the time",
        "most startups fail because of bad product not bad code",
        "nobody reads documentation. we all just try things until they work",
        "windows is actually good. people just never configure it properly",
        "the best programming language is the one that ships your product",
        "most dev twitter is just people rewriting the same take in different words",
        "your framework choice matters way less than your ability to debug",
        "junior devs with AI tools ship faster than senior devs in 2020. thats just reality",
        "remote work is better for productivity. offices are for socializing",
        "most technical interviews test things youll never use on the job",
        "the hardest part of programming isnt the code. its understanding what to build",
        "clean code is overrated. shipped code is underrated",
    ],

    "working_on": [
        "oudenOS. windows optimizer that scans hardware before changing anything. almost at v1",
        "debloating windows for the 100th time because microsoft added more telemetry",
        "trying to figure out why ndu.sys still leaks memory after 7 years",
        "a tool that shows you every windows service and what it actually does",
        "optimizing windows timer resolution from 15.6ms to 0.5ms. the difference is real",
        "nothing productive. just scrolling twitter and pretending its networking",
        "open source windows optimizer. because every bat file on reddit is sketchy",
        "rewriting something that didnt need rewriting. classic dev behavior",
        "debugging a rust lifetime issue for 3 hours. peak productivity",
        "building in public. shipping something nobody asked for. the usual",
        "a windows debloat tool that doesnt require you to trust random powershell scripts",
        "fixing bugs that only exist because microsoft ships 280 services by default",
        "learning rust by building something too ambitious. as you do",
        "automating the thing i do manually every time i fresh install windows",
        "something i cant talk about yet. but its in rust and it involves windows internals",
    ],

    "windows_vs": [
        "windows with proper optimization vs stock macOS isnt even close performance wise",
        "linux for servers. windows for desktop. mac for people who dont want to configure anything. all valid",
        "switched to mac for a year. came back to windows. missed the customization",
        "the real question isnt which OS. its whether you configured it properly",
        "linux is free if your time has no value. windows is expensive if you dont debloat it",
        "mac users: it just works. windows users: i made it work better than yours",
        "windows biggest problem isnt the OS. its the 220 services microsoft installs by default",
        "tried all three. windows with WSL is the sweet spot for dev work",
        "every OS sucks in different ways. pick the suck you can live with",
        "the windows hate is mostly from people running stock installs with 280 services",
        "linux desktop in 2026 is actually good. windows desktop in 2026 with debloat is also good",
        "mac: great laptop. windows: great desktop. linux: great server. why fight",
        "windows got WSL. mac got nothing for gaming. linux got both but needs config. pick your trade",
        "the best OS is the one you spend the least time fighting with",
        "i run windows by choice. not because i have to. because with optimization its genuinely great",
    ],

    "dev_life": [
        "the bug was a typo. it was always a typo",
        "wrote 500 lines today. deleted 400. net positive honestly",
        "git blame is just therapy for developers",
        "the code works. i dont know why. i wont touch it",
        "deploy friday is only scary if you dont have rollback",
        "most of programming is reading error messages and pretending you understand them",
        "the best code i ever wrote was code i deleted",
        "rubber duck debugging works because explaining the problem IS solving the problem",
        "production is down. again. on a friday. again",
        "the difference between junior and senior is how fast you google the same thing",
        "writing code: 20%. reading code: 30%. wondering why it works: 50%",
        "commit message: 'fixed it'. narrator: he did not fix it",
        "the real 10x developer is the one who prevents 10x the bugs",
        "your code doesnt need to be perfect. it needs to ship",
        "refactoring is just procrastinating with extra steps",
    ],

    "pc_hardware": [
        "32gb ram minimum in 2026. chrome alone wants 16",
        "nvme changed everything. boot time went from 30 seconds to 5",
        "the best upgrade you can do isnt hardware. its debloating your OS",
        "ryzen 7 + 32gb + nvme. best value build right now",
        "gpu prices are still insane. wait for next gen if you can",
        "your pc isnt slow. windows is just running 280 services you dont need",
        "before upgrading ram check task manager services tab. you might just need to disable stuff",
        "air cooling > liquid cooling for 90% of use cases. less maintenance, less risk",
        "buy the best monitor you can afford. you look at it 8+ hours a day",
        "ssd makes more difference than cpu upgrade for most people",
        "custom build > prebuilt. its not even hard anymore. youtube has everything",
        "dont cheap out on the power supply. everything depends on it",
        "16gb was fine in 2020. in 2026 its minimum. 32gb is comfortable",
        "the best gaming pc is also the best dev pc. same requirements",
        "your old pc isnt slow. it just needs a fresh windows install and debloat",
    ],

    "morning_routine": [
        "coffee, terminal, git pull. in that order",
        "check if production is still alive. then coffee",
        "open vscode, stare at code for 10 minutes, then actually start working",
        "coffee. twitter. pretend twitter is research. then actually work",
        "morning standup, then ignore everything discussed and debug yesterdays bug",
        "first thing: check if the overnight deploy broke anything. it usually did",
        "open 47 chrome tabs. close 46. start working on the one that matters",
        "wake up. mass on thanksgiving. check github notifications. mass on thanksgiving more about the issues",
        "coffee, dark mode, headphones. the holy trinity of productivity",
        "check email. delete email. actually productive day starts",
        "open task manager. wonder why windows is using 4gb at idle. debloat. start working",
        "git status. 47 files changed. mass on thanksgiving about yesterdays decisions",
        "check if the CI passed overnight. it didnt. fix it. then coffee",
        "dark mode. headphones. do not disturb. the ritual before actual productivity begins",
        "look at jira board. close jira. open vscode. real work starts now",
    ],
}


# ─── Matching logic ───────────────────────────────────────────────

_last_used: dict[str, list[int]] = {}


def match_pattern(tweet_text: str) -> str | None:
    """Match a tweet to a reply pattern. Returns pattern key or None."""
    lower = tweet_text.lower()
    for pattern_key, triggers in PATTERNS.items():
        if any(t in lower for t in triggers):
            return pattern_key
    return None


def get_canned_reply(tweet_text: str) -> str | None:
    """Get a pre-written reply for an engagement tweet. Returns None if no match."""
    pattern = match_pattern(tweet_text)
    if not pattern:
        return None

    pool = REPLIES.get(pattern, [])
    if not pool:
        return None

    # No-repeat logic: don't use same reply from last 5 in this pattern
    used = _last_used.get(pattern, [])
    available = [i for i in range(len(pool)) if i not in used]
    if not available:
        _last_used[pattern] = []
        available = list(range(len(pool)))

    idx = random.choice(available)
    _last_used.setdefault(pattern, []).append(idx)
    if len(_last_used[pattern]) > 5:
        _last_used[pattern].pop(0)

    return pool[idx]


def count_total() -> int:
    return sum(len(v) for v in REPLIES.values())
