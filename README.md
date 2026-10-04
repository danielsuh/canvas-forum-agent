# canvas-forum-agent

A Hermes Agent plugin for MIT AI Studio Homework 3: an agent that runs on a schedule, takes part in the
Homework 3: Agent Discussion Forum on https://canvas.mit.edu, remembers what it has done across runs,
and stops safely. Standard library Python only. No Canvas token is stored anywhere in this repository.

## Architecture and autonomy

```
Hermes cron (every 3 hours, runs on Hermes Cloud, no laptop needed)
   |
   v
canvas_gate.py   pre run script, no model, zero tokens
   |  reads topic -> control line RUNNING? -> not halted? -> under 3 posts this hour? -> anything new?
   |  prints {"wakeAgent": false} (agent never starts) or {"wakeAgent": true, "context": ...}
   v
Hermes agent, restricted to the canvas_forum toolset, guided by skills/forum-participation/SKILL.md
   |  canvas_forum_check  -> new entries, sanitized and labelled UNTRUSTED
   |  decides whether it has something useful to add
   |  canvas_forum_post   -> or canvas_forum_skip with a reason
   v
core.py   the only code that touches Canvas; enforces every hard rule
   |  control line check before EVERY write attempt (fail closed)
   |  max 3 posts per rolling hour
   |  intent saved to disk before the write, reconciled after any ambiguous failure
   |  GET retries with exponential backoff and jitter; writes are never blindly retried
   |  stop after 3 consecutive failed cycles (or immediately on an authentication error)
   |  verify by reading the discussion back and matching author and text
   v
Local persistent memory in ~/.hermes/canvas_agent/
      state.json     reviewed entry ids, own entry ids, post history, intents, failure counter, halt flag
      cycles.jsonl   one line per gate decision, check, post, refusal, retry, failure
```

| Requirement | Where it is met |
|---|---|
| Connect to Canvas with own token | `CANVAS_TOKEN` environment variable only, read in `core.Config.from_env` |
| Run on a schedule | Hermes cron job (see setup), gate script decides whether to wake the model |
| Persistent local memory | `state.json` written atomically with fsync, loaded on every run |
| Ignore own posts, never repeat | own entry ids and user id filter; reviewed ids; duplicate and near duplicate refusal |
| Participate meaningfully | skill instructions; agent may reply or start a thread, and may skip with a logged reason |
| No more than 3 posts per hour | `Forum.post` counts posts and pending intents in a rolling 3600 second window |
| Retries with backoff | `CanvasClient.request` (1s, 2s, 4s plus jitter, capped) and the post loop |
| Stop after repeated failures | `Forum.record_failure` sets `halted`; every tool and the gate refuse until a human runs `canvas_admin.py reset-halt` |
| Read control line before every write | `Forum.read_control` is called inside the write loop, once per attempt |
| Recover from one failure | lost acknowledgement test, plus timeout, malformed response, HTTP 500 and crash restart tests |
| Untrusted forum text | stripped of HTML and control characters, truncated, flagged, labelled; agent has no shell, file or web tools |
| Small blast radius | allow listed host, no redirects followed, one toolset, no way for the agent to edit or delete entries, no reset tool |

## Setup on Hermes Cloud

Commands below follow the Hermes docs but have not been run against a live instance by the author of this
file. Check flag names with `--help` if one is rejected.

1. Create a Canvas token: Account Settings, Approved Integrations, New Access Token. Purpose:
   `Homework 3: Agent Discussion Forum`. Expiry shortly after the due date. Copy it once.
   Never paste it into Canvas, a chat, a commit, a log or a screenshot.
2. Find the numeric ids in the forum URL: `.../courses/<COURSE_ID>/discussion_topics/<TOPIC_ID>`.
3. Put this repository on GitHub, then on the Hermes instance:
   ```
   hermes plugins install <owner>/canvas-forum-agent
   hermes plugins enable canvas-forum-agent
   ```
   The install prompts for `CANVAS_TOKEN` because the manifest declares `requires_env`.
4. Set the two ids and let them reach the gate script. Scripts get a cleaned environment, so list them:
   ```
   hermes config set terminal.env_passthrough "CANVAS_TOKEN,CANVAS_COURSE_ID,CANVAS_TOPIC_ID"
   ```
   and put `CANVAS_COURSE_ID=...` and `CANVAS_TOPIC_ID=...` in `~/.hermes/.env` (permissions 600).
5. Copy the gate script where Hermes looks for scripts:
   ```
   cp ~/.hermes/plugins/canvas-forum-agent/scripts/canvas_gate.py ~/.hermes/scripts/
   ```
6. Create the scheduled job, restricted to the plugin toolset:
   ```
   hermes cron create "0 */3 * * *" "Run one forum participation cycle using the forum-participation skill." \
     --name hw3-forum --script canvas_gate.py --skill forum-participation
   ```
   Limit the job to the `canvas_forum` toolset with `enabled_toolsets` or the `hermes tools` cron setting.
7. Test once with `/cron run <job_id>` and read the result with `python3 scripts/canvas_admin.py tail`.

Edit the PERSONA section of `skills/forum-participation/SKILL.md` to change what the agent talks about.

## Tests and failure injection

```
python3 -m unittest discover -s tests -v
```

`tests/mock_canvas.py` is a fake Canvas that can drop a response after the write lands, stall past the
timeout, return HTTP 500 or 503, return malformed JSON, return 401, and redirect. `evidence/test_run.txt`
holds a saved run of all tests.

Failure and recovery evidence (all in `tests/test_forum.py`, class `TestFailureRecovery`):

| Injected failure | Expected and tested behavior |
|---|---|
| Lost acknowledgement (write lands, connection dropped) | agent finds its own entry on the next read, records it, sends exactly one POST |
| Timeout after the write | same, one entry on the server |
| Malformed acknowledgement | same, one entry on the server |
| HTTP 500 twice then success | retried with 1s then 2s backoff, one entry |
| Crash after the write, before recording | on restart the pending intent is reconciled, a repeat post is refused as duplicate |
| Three failed cycles | agent halts, makes no network calls, a human must reset |
| Bad token (401) | halts immediately |

## Operating and stopping

* Pause everything: the course team sets the forum line to `COURSE-TEAM CONTROL: PAUSED`. You can also run
  `hermes pause`, `/cron pause <job_id>`, or stop the Hermes Cloud instance.
* Inspect: `python3 scripts/canvas_admin.py status` and `... tail 50`.
* After a halt, fix the cause, then `python3 scripts/canvas_admin.py reset-halt`.
* Runs recorded for the submission are in `~/.hermes/canvas_agent/cycles.jsonl`. Copy it out before stopping
  the instance. It contains no secrets. Redact entry text if you add any.

## Known limits

* Canvas replies deeper than the forum's threading setting may be flattened by Canvas itself.
* Only the newest 8 unreviewed entries are shown to the model per cycle; older ones are marked reviewed.
* The near duplicate check is a simple word overlap measure.
* Hermes plugin registration calls follow the public docs. Verify on your instance that the four tools and the
  skill appear (`hermes plugins list`, then ask the agent to list its tools).
