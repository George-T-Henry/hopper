# Feature request: `hopper doctor` — one-shot health check

*Written: 2026-10-02 14:31 UTC*
*Source: workspace audit of Rosetta_Program (claude:workspace-audit) on hopper 0.3.0.*

## Problem

There is no single command that answers "is Hopper healthy in this project?" During a
routine audit I had to assemble the answer by hand from `hopper sync status`,
`hopper task list`, `grep` over `.hopper/tasks/*.md`, and reading two config files.
`hopper doctor` does not exist (`No such command 'doctor'`), and `hopper maintenance` has
only `reclassify`.

The manual audit turned up exactly the kind of problems a doctor would catch:

1. **Config split-brain.** Project `.hopper/config.yaml` has `sync.enabled: false,
   server_url: null`, but sync works because `~/.hopper/config.yaml` has
   `upstream.enabled: true, server: https://hopper.henrynet.ca`. `hopper sync status`
   reports "Enabled: True". The legacy `sync:` block is inert but reads as "sync is off".
2. **Stale `in_progress` task with no owner.** `t1570ed3` was `in_progress` with no
   assignee and no heartbeat for 4 days. `task list` shows `Assigned: —` but nothing
   flags it as an ownerless claim.
3. **Long-blocked tasks.** Two tasks blocked for 114 days, depending on a retired
   subsystem. Nothing surfaces age-in-blocked.
4. **Open-task rot.** Open tasks untouched since 2026-04-25 (160+ days).
5. **Hard to count reliably.** My first in-progress count was wrong (7 vs. actual 1)
   because `task list` output is a wrapped Rich table; no cheap `--count`/summary.

## Proposal

`hopper doctor [--json] [--fix] [--stale-days N]`

Read-only by default. Exit code 0 = all OK, 1 = warnings, 2 = errors (so it works in
cron/CI and agent session-start hooks). Output is grouped, one line per check, with a
suggested remedy command.

### Checks (suggested v1)

**Config**
- Project config and global config disagree on sync (`sync.enabled` vs `upstream.enabled`);
  report the *effective* sync target and which file it came from.
- Config file referenced paths exist (`storage.path`, `did_key_path`).
- Instance id/name match the directory they live in.

**Sync**
- Upstream reachable; DID key present and valid.
- Last sync age (warn if > N hours); local-only task writes pending push.

**Tasks**
- `in_progress` with no assignee, or no heartbeat for > N days (default 2).
- `blocked` for > N days (default 30), with its blocking reason/tags.
- `open` untouched for > N days (default 90) — count plus oldest few.
- Assignee uses a generic identity (`main`, empty) instead of `platform:task-name`.
- Dangling `depends:` references to missing tasks.
- Summary counts by status (this is also what I needed and didn't have).

**Environment / agent files**
- `.hopper/` is gitignored where expected (or deliberately tracked).
- `AGENTS.md` / `CLAUDE.md` Hopper section matches the installed version's template
  (`hopper knowledge update-agent-files` would change something).
- CLI version vs. server version desync (already noted in the 2026-09-12 follow-up).
- Legacy tag-encoded records that `hopper maintenance reclassify` would migrate (count).

### `--fix` (opt-in, conservative)

Only mechanical, reversible fixes, each printed before it runs:
- Release ownerless/stale `in_progress` tasks to `open` with an attributed note.
- Annotate or remove the inert legacy `sync:` block.
- Run `reclassify` when legacy records are found.

Never closes, deletes, or re-prioritizes tasks.

## Acceptance

- `hopper doctor` runs in < 2 s on a ~220-task board and works offline (sync checks
  degrade to a warning, not a failure).
- `--json` emits one object per check: `{id, status: ok|warn|error, message, remedy}`.
- Running it on the Rosetta_Program board as of 2026-10-02 (before the cleanup) would
  have reported items 1–4 above.

## Non-goals

- Not a replacement for `hopper sync status` / `hopper context`; it should call into them.
- No automatic task closure or reprioritization.
