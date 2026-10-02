"""Tests for agent/programmatic UX: --json, full IDs, --assignee, --id-only."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from hopper.cli.main import cli


@pytest.fixture
def isolated_runner():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmpdir:
        hopper_dir = Path(tmpdir) / ".hopper"
        hopper_dir.mkdir()
        (hopper_dir / "tasks").mkdir()
        yield runner


def _add(runner, title, *extra):
    result = runner.invoke(cli, ["task", "add", title, "--non-interactive", "--id-only", *extra])
    assert result.exit_code == 0, result.output
    return result.output


LONG_TITLE = "RCP test-pattern generation with a very long descriptive title " * 3


def test_id_only_prints_just_the_id(isolated_runner):
    out = _add(isolated_runner, "hello")
    task_id = out.strip()
    assert out == task_id + "\n"
    assert " " not in task_id
    result = isolated_runner.invoke(cli, ["task", "get", task_id, "--json"])
    assert json.loads(result.output)["id"] == task_id


def test_list_json_full_fields(isolated_runner):
    task_id = _add(isolated_runner, LONG_TITLE, "-d", "a long description " * 20).strip()
    result = isolated_runner.invoke(cli, ["task", "list", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [t["id"] for t in data] == [task_id]
    assert data[0]["title"] == LONG_TITLE
    assert data[0]["description"].startswith("a long description")


def test_global_json_still_works(isolated_runner):
    _add(isolated_runner, "one")
    result = isolated_runner.invoke(cli, ["--json", "task", "list"])
    assert len(json.loads(result.output)) == 1


def test_get_json_after_subcommand(isolated_runner):
    task_id = _add(isolated_runner, "one").strip()
    result = isolated_runner.invoke(cli, ["task", "get", task_id, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["title"] == "one"


def test_assignee_filter_exact_and_prefix(isolated_runner):
    a = _add(isolated_runner, "a", "--assign", "claude:foo").strip()
    b = _add(isolated_runner, "b", "--assign", "claude:bar").strip()
    _add(isolated_runner, "c", "--assign", "human:james")
    _add(isolated_runner, "d")

    def ids(*args):
        r = isolated_runner.invoke(cli, ["task", "list", "--ids-only", *args])
        assert r.exit_code == 0, r.output
        return set(r.output.split())

    assert ids("--assignee", "claude:foo") == {a}
    assert ids("--assignee", "claude:") == {a, b}
    assert ids("--assignee", "nobody") == set()


def test_assignee_filter_applies_before_limit(isolated_runner):
    # Unassigned tasks created later sort first by default; they must not push
    # the assignee's tasks out of a small --limit window.
    mine = {_add(isolated_runner, f"m{i}", "--assign", "claude:me").strip() for i in range(3)}
    for i in range(5):
        _add(isolated_runner, f"other{i}")
    r = isolated_runner.invoke(
        cli, ["task", "list", "--ids-only", "--assignee", "claude:me", "--limit", "3"]
    )
    assert r.exit_code == 0, r.output
    assert set(r.output.split()) == mine


@pytest.mark.parametrize("compact", [False, True])
def test_table_shows_full_id(isolated_runner, compact):
    task_id = _add(isolated_runner, "short").strip()
    args = ["task", "list"] + (["--compact"] if compact else [])
    result = isolated_runner.invoke(cli, args, env={"COLUMNS": "60"})
    assert result.exit_code == 0, result.output
    assert task_id in result.output
