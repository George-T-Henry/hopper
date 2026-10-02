"""CI check: this repo's own agent files must not drift behind the generator."""

import re
from pathlib import Path

import pytest

from hopper.storage.knowledge import AGENTS_MD_SECTION, AGENTS_MD_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("filename", ["AGENTS.md", "CLAUDE.md"])
def test_repo_agent_files_at_current_template_version(filename):
    content = (REPO_ROOT / filename).read_text()
    match = re.search(r"<!-- hopper-agent-files: v(\d+) -->", content)
    assert match, f"{filename} has no hopper-agent-files version marker"
    assert int(match.group(1)) == AGENTS_MD_VERSION, (
        f"{filename} is at v{match.group(1)} but the generator is at "
        f"v{AGENTS_MD_VERSION}; refresh the Hopper section of {filename} "
        "(see write_agent_files in hopper.storage.knowledge)"
    )


@pytest.mark.parametrize("filename", ["AGENTS.md", "CLAUDE.md"])
def test_repo_agent_files_contain_current_section(filename):
    assert AGENTS_MD_SECTION.strip() in (REPO_ROOT / filename).read_text()


def test_claude_md_still_points_to_agents_md():
    assert "AGENTS.md" in (REPO_ROOT / "CLAUDE.md").read_text().split("## Hopper - Persistent")[0]
