"""A timed-out MCP call must not discard earlier pages in the batch."""

import shutil
from types import SimpleNamespace

import pytest

from wsp_core import http_client, provider_registry


@pytest.mark.parametrize("request_expired", [True, False], ids=["request-deadline", "attempt-cap"])
def test_batch_timeout_keeps_completed_pages_and_closes_session(monkeypatch, request_expired):
    spec = provider_registry.PROVIDER_SPECS["donsetch"]
    module = spec.execute_extract.__globals__
    urls = [f"https://example.org/{part}" for part in ("done", "slow", "not-started")]
    clock = SimpleNamespace(value=100.0)
    sessions = []

    class FakeSession:
        def __init__(self, _binary, timeout):
            self.timeout = timeout
            self.closed = False
            self.calls = []
            sessions.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            self.closed = True
            return False

        def call(self, tool, arguments):
            assert not self.closed
            assert tool == "web_fetch"
            self.calls.append(arguments["url"])
            if len(self.calls) == 1:
                clock.value += 0.3
                return {
                    "structured": {"url": urls[0], "content_ok": True, "status": 200},
                    "text": "already fetched",
                }
            assert len(self.calls) == 2, "a timed-out MCP session must never be reused"
            clock.value = 101.5
            raise TimeoutError

    monkeypatch.setitem(module, "DonsetchSession", FakeSession)
    monkeypatch.setattr(http_client, "time", SimpleNamespace(monotonic=lambda: clock.value))
    deadline = 101.5 if request_expired else 110.0
    with http_client.request_deadline_scope(deadline), http_client.request_timeout_cap(1.5):
        result = spec.execute_extract(
            None, "donsetch", urls, shutil.which("true"), "markdown",
            False, False, False, {}, False,
        )

    assert len(sessions) == 1
    assert sessions[0].timeout == pytest.approx(1.5)
    assert sessions[0].closed
    assert sessions[0].calls == urls[:2]
    assert result["provider"] == "donsetch"
    assert [item["url"] for item in result["results"]] == urls
    assert result["results"][0]["content"] == "already fetched"
    assert result["results"][1]["error"] == "donsetch_timeout"
    assert result["results"][2]["error"] == http_client.NOT_TRIED_DEADLINE_ERROR
