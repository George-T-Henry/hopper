"""Tests for editable_install_status using throwaway git repos."""

import subprocess
from pathlib import Path

from hopper.utils.install import editable_install_status


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    _git(repo, "add", name)
    _git(repo, "commit", "-m", name)


def _make_clone(tmp_path: Path) -> Path:
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-b", "main")
    _commit(origin, "a")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", str(origin), str(clone))
    return clone


def test_not_a_git_repo(tmp_path):
    assert editable_install_status(tmp_path) is None


def test_missing_directory_does_not_raise(tmp_path):
    assert editable_install_status(tmp_path / "nope") is None


def test_up_to_date(tmp_path):
    clone = _make_clone(tmp_path)
    status = editable_install_status(clone)
    assert status["branch"] == "main"
    assert status["default_ref"] == "origin/main"
    assert status["behind"] == 0
    assert status["ahead"] == 0


def test_stale_feature_branch_counts_commits_behind(tmp_path):
    clone = _make_clone(tmp_path)
    _git(clone, "checkout", "-b", "feat/old")
    # Advance main on the remote side, then fetch.
    origin = tmp_path / "origin"
    _commit(origin, "b")
    _commit(origin, "c")
    _git(clone, "fetch", "origin")
    status = editable_install_status(clone)
    assert status["branch"] == "feat/old"
    assert status["behind"] == 2
    assert status["ahead"] == 0


def test_local_only_repo_has_no_default_ref(tmp_path):
    repo = tmp_path / "solo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _commit(repo, "a")
    status = editable_install_status(repo)
    assert status["branch"] == "main"
    assert status["default_ref"] is None
    assert status["behind"] is None


def test_detached_head(tmp_path):
    clone = _make_clone(tmp_path)
    _git(clone, "checkout", "--detach")
    assert editable_install_status(clone)["branch"] is None
