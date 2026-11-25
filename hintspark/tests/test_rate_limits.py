"""Security regression tests for rate limiting.

1. The client must not be able to choose its own rate-limit identity by
   sending a fake X-Forwarded-For header.
2. The limiter's memory must stay bounded when an attacker rotates identities.
3. /api/event must be rate limited (it writes to the analytics database).
"""
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.main import RateLimiter, app, client_key


def fake_request(xff=None, peer="9.9.9.9"):
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def test_spoofed_forwarded_for_is_ignored_by_default(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    assert client_key(fake_request(xff="1.2.3.4")) == "9.9.9.9"


def test_behind_one_proxy_uses_the_address_the_proxy_added(monkeypatch):
    # The client can put anything at the FRONT; the trusted proxy APPENDS the real address.
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    assert client_key(fake_request(xff="1.2.3.4, 5.6.7.8")) == "5.6.7.8"


def test_invalid_proxy_hops_setting_falls_back_safely(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "not-a-number")
    assert client_key(fake_request(xff="1.2.3.4")) == "9.9.9.9"


def test_limiter_memory_is_bounded():
    limiter = RateLimiter(5, 60, max_keys=100)
    for i in range(1000):
        limiter.check(f"attacker-{i}")
    assert len(limiter.hits) <= 100


def test_event_endpoint_is_rate_limited():
    client = TestClient(app)
    body = {"session_id": "s1", "exercise_id": "ex1", "event_type": "open"}
    codes = [client.post("/api/event", json=body).status_code for _ in range(80)]
    assert 429 in codes, "/api/event accepted 80 requests in a row with no rate limit"
