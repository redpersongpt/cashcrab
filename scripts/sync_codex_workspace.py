#!/usr/bin/env python3
"""Write CashCrab skill packs and agent roles into a workspace."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules import agentpacks


def main() -> int:
    target = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.cwd()
    result = agentpacks.sync_workspace(target)
    print(f"Synced {result['skills']} skills and {result['agents']} agents into {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
