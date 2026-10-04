#!/usr/bin/env python3
"""Pre run gate for the Hermes cron job. Runs with no model and costs no tokens.

Prints one JSON line on stdout:
  {"wakeAgent": false}                      -> Hermes skips the model this tick
  {"wakeAgent": true, "context": {...}}     -> Hermes runs the agent

It wakes the agent only when the forum is RUNNING, the agent is not halted, the hourly post
limit is not used up, and there is something new to read (or the agent has been quiet long
enough to consider an original post). Exit code 1 means an error worth an alert.
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


def main():
    try:
        forum = core.Forum(core.Config.from_env())
        result = forum.gate()
    except core.ConfigError as e:
        print("config error: %s" % e)
        return 1
    except core.CanvasError as e:
        print("canvas error (%s): %s" % (e.kind, e))
        return 1
    out = {"wakeAgent": bool(result["wake"])}
    if result["wake"]:
        out["context"] = {k: v for k, v in result.items() if k != "wake"}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
