"""Terminal UI helpers for the colorful CashCrab CLI."""

import os
from pathlib import Path

from rich.console import Console
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich import box

_theme = Theme({
    "ok": "bold green",
    "err": "bold red",
    "warn": "bold yellow",
    "hint": "bold bright_cyan",
    "step": "bold bright_magenta",
    "brand": "bold bright_white",
    "money": "bold bright_green",
    "hot": "bold bright_red",
    "metal": "bold bright_yellow",
})

console = Console(theme=_theme)

MASCOT_ART = [
    "[hot]        __      __[/hot]",
    "[hot]   ___ /  \\____/  \\ ___[/hot]",
    "[hot]  /   /  $  __  $  \\   \\[/hot]",
    "[hot] |   |  .-.(  ).-.  |   |[/hot]",
    "[hot] |   |  |$| \\/ |$|  |   |[/hot]",
    "[hot]  \\__ \\  '--.--'  / __/[/hot]",
    "[hot]     \\_\\_/ /\\ \\_/_/[/hot]",
    "[hot]        /_/  \\_\\[/hot]",
]


def _mini_mascot():
    """Render a tiny version of the mascot inside the terminal banner."""
    mascot_path = Path(__file__).resolve().parent.parent / "assets" / "cashcrab_48x48.png"
    try:
        from PIL import Image

        img = Image.open(mascot_path).convert("RGBA").resize((10, 10), Image.NEAREST)
        lines = []
        for y in range(img.height):
            line = Text()
            for x in range(img.width):
                r, g, b, a = img.getpixel((x, y))
                if a < 40:
                    line.append("  ")
                else:
                    line.append("  ", style=f"on rgb({r},{g},{b})")
            lines.append(line)
        return Group(*lines)
    except Exception:
        return Text.from_markup("\n".join(MASCOT_ART))


def clear():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    """Show the CashCrab hero panel."""
    mascot = _mini_mascot()

    copy = Group(
        Text.from_markup("[brand]CASHCRAB[/brand]  [money]terminal autopilot[/money]"),
        Text.from_markup("[bold]Simple by default.[/bold] Run the app, pick a number, follow the prompts."),
        Text.from_markup("[dim]No command memory test. No hidden steps. 0 always goes back.[/dim]"),
        Text.from_markup("[metal]Fast path:[/metal] Setup accounts -> pick a workflow -> press Enter."),
    )

    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(width=22)
    grid.add_column(ratio=1)
    grid.add_row(mascot, copy)

    console.print()
    console.print(
        Panel(
            grid,
            box=box.DOUBLE,
            border_style="hot",
            padding=(1, 2),
            title="[money]CashCrab CLI[/money]",
            subtitle="[dim]Pick a number. Enter confirms. Ctrl+C cancels.[/dim]",
        )
    )
    console.print()


def menu(title: str, options: list[str], back_label: str = "Go back") -> int:
    """Show a numbered menu. Returns 1..N for options, 0 for back/exit."""
    rows = Table.grid(expand=True)
    rows.add_column(width=6)
    rows.add_column(ratio=1)

    for i, label in enumerate(options, 1):
        rows.add_row(f"[money]{i:>2}[/money]", f"[bold]{label}[/bold]")

    rows.add_row("[dim] 0[/dim]", f"[dim]{back_label}[/dim]")

    console.print(
        Panel(
            rows,
            title=f"[brand]{title}[/brand]",
            border_style="hint",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print("  [dim]Type the menu number and press Enter.[/dim]\n")

    while True:
        try:
            raw = console.input("  [brand]Pick a number:[/brand] ").strip()
            if raw == "":
                continue
            n = int(raw)
            if 0 <= n <= len(options):
                return n
            console.print(f"  [warn]Please type a number from 0 to {len(options)}.[/warn]")
        except ValueError:
            console.print(f"  [warn]That's not a number. Type 0 to {len(options)}.[/warn]")
        except (KeyboardInterrupt, EOFError):
            return 0


def success(msg: str):
    """Green success message."""
    console.print(f"\n  [ok]OK[/ok]  {msg}")


def fail(msg: str):
    """Red error message."""
    console.print(f"\n  [err]ERROR[/err]  {msg}")


def warn(msg: str):
    """Yellow warning message."""
    console.print(f"  [warn]WARNING[/warn]  {msg}")


def info(msg: str):
    """Cyan info/hint message."""
    console.print(f"  [hint]>>[/hint] {msg}")


def step(n: int, total: int, msg: str):
    """Step progress indicator: Step 2/5: Doing something..."""
    console.print(f"\n  [step]Step {n}/{total}[/step]  {msg}")


def ask(prompt: str, default: str = "") -> str:
    """Ask for text input. Returns default if user presses Enter."""
    hint = f" [dim](default: {default})[/dim]" if default else ""
    val = console.input(f"  [brand]{prompt}[/brand]{hint}: ").strip()
    return val if val else default


def ask_or_skip(prompt: str) -> str | None:
    """Ask for optional input. Returns None if skipped."""
    val = console.input(f"  [brand]{prompt}[/brand] [dim](press Enter to skip)[/dim]: ").strip()
    return val if val else None


def confirm(prompt: str, default: bool = True) -> bool:
    """Yes/no question. Returns True or False."""
    hint = "Y/n" if default else "y/N"
    val = console.input(f"  [brand]{prompt}[/brand] [dim]({hint})[/dim]: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")


def pause(msg: str = "Press Enter to continue..."):
    """Wait for user to press Enter."""
    console.input(f"\n  [dim]{msg}[/dim]")


def divider():
    """Print a thin horizontal line."""
    console.print("  " + "-" * 40, style="dim")


def status_table(rows: list[tuple[str, str, str]]):
    """Display a status table. rows = [(name, status_text, detail), ...]"""
    table = Table(box=box.SIMPLE, padding=(0, 2), show_edge=False)
    table.add_column("Service", style="bold")
    table.add_column("Status")
    table.add_column("", style="dim")

    for name, st, detail in rows:
        good = ("connected", "valid", "set", "ok", "ready", "saved")
        bad = ("not", "missing", "none", "empty", "expired", "corrupt")
        if any(w in st.lower() for w in good):
            color = "green"
        elif any(w in st.lower() for w in bad):
            color = "red"
        else:
            color = "yellow"
        table.add_row(name, f"[{color}]{st}[/{color}]", detail)

    console.print()
    console.print(table)
    console.print()
