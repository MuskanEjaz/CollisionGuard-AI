# test_cors.py -- Phase 8 CORS preflight verification
#
# A direct DELETE returning HTTP 200 does NOT prove that browser CORS works.
# Browsers first send an OPTIONS preflight with:
#   Origin: <frontend origin>
#   Access-Control-Request-Method: DELETE
#
# The server must respond with:
#   Access-Control-Allow-Origin: <frontend origin>
#   Access-Control-Allow-Methods: (includes DELETE)
#
# Only then will the browser send the actual DELETE.
# These tests verify that the server correctly handles the preflight.
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

FRONTEND_ORIGIN = "http://localhost:5173"


def test_cors_preflight_delete_cache_returns_200():
    # Browser-style OPTIONS preflight for DELETE /scenarios/{id}/cache.
    # FastAPI + Starlette respond to preflight with 200.
    r = client.options(
        "/scenarios/CONJ-001/cache",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200, (
        f"OPTIONS preflight failed with {r.status_code}. "
        f"Browser will block the DELETE. Check CORSMiddleware allow_methods."
    )


def test_cors_preflight_delete_allows_origin():
    # The ACAO header must echo the frontend origin (or *).
    r = client.options(
        "/scenarios/CONJ-001/cache",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "DELETE",
        },
    )
    acao = r.headers.get("access-control-allow-origin", "")
    assert FRONTEND_ORIGIN in acao or acao == "*", (
        f"Access-Control-Allow-Origin missing or wrong: {acao!r}. "
        f"Browser will block cross-origin DELETE."
    )


def test_cors_preflight_delete_allows_delete_method():
    # The ACAM header must include DELETE.
    r = client.options(
        "/scenarios/CONJ-001/cache",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "DELETE",
        },
    )
    acam = r.headers.get("access-control-allow-methods", "")
    assert "DELETE" in acam.upper(), (
        f"Access-Control-Allow-Methods missing DELETE: {acam!r}. "
        f"Browser will block cross-origin DELETE even if preflight returns 200."
    )


def test_cors_delete_actually_works():
    # Sanity check: the actual DELETE endpoint also returns 200.
    # This alone is not sufficient CORS proof -- see preflight tests above.
    r = client.delete(
        "/scenarios/CONJ-001/cache",
        headers={"Origin": FRONTEND_ORIGIN},
    )
    assert r.status_code == 200


def test_cors_preflight_get_still_works():
    # Regression: adding DELETE must not break existing GET CORS.
    r = client.options(
        "/scenarios",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    acao = r.headers.get("access-control-allow-origin", "")
    assert FRONTEND_ORIGIN in acao or acao == "*"


def test_cors_preflight_post_still_works():
    # Regression: adding DELETE must not break existing POST CORS.
    r = client.options(
        "/scenarios/CONJ-001/analyse",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
