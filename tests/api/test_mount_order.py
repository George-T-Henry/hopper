"""Route/health regressions for the main API app."""

from hopper import __version__
from hopper.api.app import create_app


def test_sse_mount_registered_before_streamable_http():
    paths = [getattr(r, "path", None) for r in create_app().routes]
    assert paths.index("/mcp/sse") < paths.index("/mcp")


def test_health_reports_real_version():
    from fastapi.testclient import TestClient

    assert TestClient(create_app()).get("/health").json()["version"] == __version__
