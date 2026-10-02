# Changelog

## 0.4.0 — 2026-10-02

### Added
- `hopper doctor [--json] [--fix] [--stale-days N]`: one-shot health check
  (config split-brain, sync, task hygiene, environment) with exit codes
  0/1/2. `--fix` is conservative and prints each action first. (#10)
- `hopper sync --batch-size N` and `--dry-run`; `upstream.batch_size` config
  key. `--dry-run` shows pending local changes and approximate size.
- `task list --json` / `--assignee`, `task get --json`, `task add --id-only`;
  `task list` shows full task IDs.
- `hopper --version` also shows the packaging-resolved version and warns on
  mismatch.
- GitHub issue templates (bug, feature request, agent UX feedback). (#8)
- Server `/health` now reports the real hopper version.

### Fixed
- Sync no longer fails with a raw nginx 413 page on large backlogs: pushes
  are batched with a resumable cursor, a 413 halves the batch and retries,
  and errors are one line. Pulls are paged too (`pull_limit`, `has_more`,
  `next_since`; needs a 0.4 server to take effect). (#9)
- CI: depend on `sqlalchemy[asyncio]` so `greenlet` is installed.
- Work with SQLAlchemy 2.1: bare `postgresql://` now uses psycopg2; in-memory
  SQLite is detected for `reset_database_dev_only`.
- `--version` metadata lookup used the wrong distribution name and could read
  a stale `hopper.egg-info`.
- `/mcp/sse` was shadowed by the `/mcp` mount.
- Per-request MCP session bookkeeping no longer leaks entries.

### Changed
- **Requires `mcp>=2.0.0,<3`** (was `<2`); MCP code migrated to the v2 SDK. (#7)
- Generated agent files are template v3 (adds the new task flags).

### Compatibility
- Sync protocol changes are additive: 0.4 clients work with older servers and
  the reverse. Older servers simply don't page pulls.
