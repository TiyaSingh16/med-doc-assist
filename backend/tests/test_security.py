import time

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.utils.rate_limit import SlidingWindowLimiter


def test_app_refuses_to_start_without_a_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("value", ["dev-secret-key", "short"])
def test_placeholder_or_short_secret_keys_are_rejected(monkeypatch, value):
    monkeypatch.setenv("SECRET_KEY", value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_sliding_window_limiter_frees_slots_as_time_passes():
    now = [0.0]
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60, clock=lambda: now[0])
    assert limiter.check("u") is None
    assert limiter.check("u") is None
    assert limiter.check("u") == pytest.approx(60)
    assert limiter.check("other-user") is None
    now[0] = 60.0
    assert limiter.check("u") is None


def test_login_does_not_reveal_which_emails_exist(client):
    """Unknown email and wrong password take comparable time (bcrypt runs in both)."""
    client.post("/auth/register", json={"email": "real@example.com", "password": "password123"})

    def timed(email):
        start = time.perf_counter()
        response = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        assert response.status_code == 401
        return time.perf_counter() - start

    unknown = min(timed("nobody@example.com") for _ in range(3))
    known = min(timed("real@example.com") for _ in range(3))
    assert unknown > known * 0.5
