"""Plain pytest unit tests — no Aito calls, no snapshots.

Use this file for things that don't depend on external services.
For Aito-dependent tests, use booktest in book/ (snapshot pattern keeps
them fast + deterministic).
"""

from fastapi.testclient import TestClient

from src.app import app

client = TestClient(app)


def test_health_endpoint_returns_ok():
    """/health is the cheap liveness probe nginx routes to.

    Must stay cheap (no Aito call) and stable — external monitoring depends
    on it.
    """
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
