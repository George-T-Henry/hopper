"""Version reporting helpers.

``hopper.__version__`` is hardcoded in source, while ``importlib.metadata``
reports whatever version packaging resolved at install time. On editable
installs these can disagree, so ``hopper --version`` shows both.
"""

from __future__ import annotations

from importlib import metadata


def packaging_version() -> str | None:
    """Return the version recorded in installed package metadata, or None."""
    try:
        return metadata.version("hopper")
    except Exception:
        return None


def version_report(source_version: str) -> tuple[str, bool]:
    """Build the ``--version`` text and whether the two versions mismatch."""
    pkg = packaging_version()
    text = f"hopper, version {source_version}"
    if pkg is None:
        return text + " (packaging metadata: unavailable)", False
    text += f" (packaging metadata: {pkg})"
    if pkg != source_version:
        return (
            text + f"\nWARNING: version mismatch: source says {source_version}, "
            f"installed metadata says {pkg}. Trust the source version; "
            "reinstall (pip install -e .) to refresh metadata.",
            True,
        )
    return text, False
