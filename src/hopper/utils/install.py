"""Editable/source-install status detection (standalone, failure-tolerant)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

_GIT_TIMEOUT = 3


def _git(repo: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _default_remote_ref(repo: Path) -> str | None:
    """Find origin's default branch ref using only local data (no network)."""
    head = _git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if head:
        return head.removeprefix("refs/remotes/")
    for name in ("origin/main", "origin/master"):
        if _git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/{name}"):
            return name
    return None


def editable_install_status(package_dir: Path | None = None) -> dict[str, Any] | None:
    """Describe the source checkout hopper is running from.

    Returns None when not running from a git source checkout (e.g. a wheel
    install) or when git is unavailable. Otherwise a dict with keys:
    ``repo`` (str), ``branch`` (str, or None if detached), ``commit`` (short
    sha), ``default_ref`` (e.g. ``origin/master``, or None), and
    ``behind``/``ahead`` (int, or None when no remote default is known).
    Uses local refs only (no fetch), so it is fast and offline-safe; the
    comparison is as fresh as the last ``git fetch``. Never raises.
    """
    try:
        start = Path(package_dir) if package_dir else Path(__file__).resolve().parent
        top = _git(start, "rev-parse", "--show-toplevel")
        if not top:
            return None
        repo = Path(top)
        branch = _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
        commit = _git(repo, "rev-parse", "--short", "HEAD")
        ref = _default_remote_ref(repo)
        behind = ahead = None
        if ref:
            counts = _git(repo, "rev-list", "--left-right", "--count", f"HEAD...{ref}")
            if counts:
                left, right = counts.split()
                ahead, behind = int(left), int(right)
        return {
            "repo": str(repo),
            "branch": branch or None,
            "commit": commit,
            "default_ref": ref,
            "behind": behind,
            "ahead": ahead,
        }
    except Exception:
        return None
