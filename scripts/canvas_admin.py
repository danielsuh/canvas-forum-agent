#!/usr/bin/env python3
"""Human only controls. The agent has no tool that can do any of this.

  python3 canvas_admin.py status        show counters and halt state
  python3 canvas_admin.py tail [N]      show the last N log lines (default 20)
  python3 canvas_admin.py reset-halt    clear a halt after you have fixed the cause
"""
import json
import os
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
for cand in (os.environ.get("CANVAS_PLUGIN_DIR"), str(Path.home() / ".hermes" / "plugins" / "canvas-forum-agent"),
             str(here.parent)):
    if cand and (Path(cand) / "core.py").exists():
        sys.path.insert(0, cand)
        break

import core  # noqa: E402


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    home = os.environ.get("CANVAS_AGENT_HOME") or str(Path.home() / ".hermes" / "canvas_agent")
    state = core.State(home)
    if cmd == "tail":
        n = int(argv[2]) if len(argv) > 2 else 20
        lines = state.log_path.read_text().splitlines()[-n:] if state.log_path.exists() else []
        print("\n".join(lines))
        return 0
    cfg = core.Config("x", "1", "1", base_url="http://127.0.0.1", state_dir=home)  # no network used here
    forum = core.Forum(cfg, state=state)
    if cmd == "reset-halt":
        forum.reset_halt()
        print("halt cleared")
    print(json.dumps(forum.status(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
