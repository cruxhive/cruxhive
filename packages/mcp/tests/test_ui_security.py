"""Security regression tests for the local dashboard.

The UI is unauthenticated and exposes state-changing endpoints, so it relies on
a Host-header allowlist to resist DNS-rebinding. Skips cleanly if the [ui] extra
(fastapi/starlette/httpx) isn't installed.
"""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("starlette.testclient")

from starlette.testclient import TestClient

from cruxhive_mcp.ui import make_app


@pytest.fixture
def client():
    return TestClient(make_app())


def test_loopback_hosts_allowed(client):
    assert client.get("/", headers={"host": "localhost:3847"}).status_code == 200
    assert client.get("/api/pending", headers={"host": "127.0.0.1:3847"}).status_code == 200


def test_foreign_host_blocked_on_read(client):
    # DNS-rebinding: attacker's hostname resolved to 127.0.0.1 → Host mismatch.
    assert client.get("/", headers={"host": "evil.attacker.com"}).status_code == 400


def test_foreign_host_blocked_on_privileged_write(client):
    r = client.post(
        "/api/approve",
        headers={"host": "evil.attacker.com"},
        json={"path": "x", "approver": "y"},
    )
    assert r.status_code == 400
