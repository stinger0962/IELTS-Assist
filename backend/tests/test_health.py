"""The /api/health endpoint backs the uptime monitor.

/health alone is not reachable in production: nginx proxies only /api/*, so a
root-level health route is served by the SPA catch-all instead of the backend.
"""


def test_api_health_reports_healthy(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["database"] == "ok"
    assert "version" in body


def test_api_health_needs_no_auth(client):
    """A monitor must not have to hold credentials."""
    assert client.get("/api/health").status_code == 200


def test_root_health_still_works(client):
    assert client.get("/health").status_code == 200
