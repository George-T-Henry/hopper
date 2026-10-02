"""Tests for `hopper --version` and packaging-version comparison."""

from unittest.mock import patch

from hopper import __version__
from hopper.utils import version as version_mod
from hopper.utils.version import version_report


def test_report_match():
    with patch.object(version_mod, "packaging_version", return_value=__version__):
        text, mismatch = version_report(__version__)
    assert not mismatch
    assert f"packaging metadata: {__version__}" in text
    assert "WARNING" not in text


def test_report_mismatch_is_flagged():
    with patch.object(version_mod, "packaging_version", return_value="0.0.1"):
        text, mismatch = version_report("9.9.9")
    assert mismatch
    assert "WARNING: version mismatch" in text
    assert "9.9.9" in text and "0.0.1" in text


def test_report_metadata_unavailable():
    with patch.object(version_mod, "packaging_version", return_value=None):
        text, mismatch = version_report("1.2.3")
    assert not mismatch
    assert "unavailable" in text


def test_cli_version_flag_shows_both():
    from click.testing import CliRunner

    from hopper.cli.main import cli

    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert f"version {__version__}" in result.output
    assert "packaging metadata" in result.output
