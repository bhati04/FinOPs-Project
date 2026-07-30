"""Health API contract tests."""

from httpx import AsyncClient

from cloudwise.main import app
from cloudwise.platform_health.service import HealthService, get_health_service


async def succeeds() -> bool:
    return True


async def fails() -> bool:
    return False


async def test_liveness_has_security_and_correlation_headers(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-correlation-id"]


async def test_liveness_replaces_invalid_correlation_id(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live", headers={"X-Correlation-ID": "unsafe-value"})

    assert response.status_code == 200
    assert response.headers["x-correlation-id"] != "unsafe-value"


async def test_readiness_is_ready_when_dependencies_are_up(client: AsyncClient) -> None:
    app.dependency_overrides[get_health_service] = lambda: HealthService(succeeds, succeeds)
    try:
        response = await client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": {"status": "up"}, "redis": {"status": "up"}},
    }


async def test_readiness_is_unavailable_when_dependency_is_down(client: AsyncClient) -> None:
    app.dependency_overrides[get_health_service] = lambda: HealthService(succeeds, fails)
    try:
        response = await client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["redis"]["status"] == "down"


async def test_oversized_request_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/health/live",
        headers={"Content-Length": "9999999"},
        content=b"",
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large"}


async def test_api_documentation_allows_only_required_cdn_assets(client: AsyncClient) -> None:
    response = await client.get("/api/docs")

    assert response.status_code == 200
    policy = response.headers["content-security-policy"]
    assert "script-src https://cdn.jsdelivr.net" in policy
    assert "frame-ancestors 'none'" in policy
