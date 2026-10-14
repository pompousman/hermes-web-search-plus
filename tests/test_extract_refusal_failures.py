"""URL refusals survive provider and wrapper failures, without rescue leaks."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from plugin_loader import load_plugin
from test_native_backend import backend as backend
from wsp_core import extract, providers


REFUSED = [
    "http://127.0.0.1/admin", "http://localhost/", "http://169.254.169.254/meta",
    "http://[::1]/", "http://10.0.0.5/", "http://0x7f.1/",
    "HTTP://127.0.0.1/", " http://10.0.0.5/ ", "http:///x",
    "file:///etc/passwd", "ftp://intranet.example.org/a", "gopher://127.0.0.1:6379/_INFO",
]


@pytest.mark.parametrize("refused", REFUSED)
@pytest.mark.parametrize("failure", ["exception", "5xx", "timeout", "unmatched", "generic"])
def test_native_preflight_refusal_survives_failure(backend, refused, failure):
    public = "https://example.org/a"
    if failure in {"exception", "timeout"}:
        backend.plugin._run_extract.side_effect = (
            TimeoutError("deadline") if failure == "timeout" else RuntimeError("provider failed")
        )
    else:
        backend.plugin._run_extract.return_value = {
            "5xx": {"results": [{"url": public, "error": "HTTP 503"}]},
            "unmatched": {"results": [{"url": "https://example.org/stray", "content": "stray"}]},
            "generic": {"results": [], "error": "All extraction providers failed"},
        }[failure]
    rows = backend.value.extract([refused, public])
    assert [r["url"] for r in rows] == [refused, public]
    assert rows[0].get("blocked_by_policy") and rows[0].get("error")
    assert "blocked_by_policy" not in rows[1]
    assert backend.plugin._run_extract.call_args.args[0] == [public]


def test_native_preflight_normalizes_public_scheme_and_space(backend):
    requested = " HTTPS://example.org/a "
    backend.plugin._run_extract.return_value = {
        "results": [{"url": "https://example.org/a", "content": "body"}]
    }
    row = backend.value.extract([requested])[0]
    assert row["url"] == requested and row["content"] == "body"
    assert backend.plugin._run_extract.call_args.args[0] == ["https://example.org/a"]


@pytest.mark.parametrize("failure", ["exception", "5xx", "unmatched"])
def test_engine_failure_retains_refused_urls(monkeypatch, failure):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    fake = Mock(side_effect=RuntimeError("provider failed")) if failure == "exception" else Mock(return_value={
        "provider": "tavily", "results": [
            {"url": "https://example.org/a", "error": "HTTP 503"}
            if failure == "5xx" else {"url": "https://example.org/stray", "content": "stray"}
        ],
    })
    monkeypatch.setattr(providers, "extract_tavily", fake)
    # Two public URLs keep a lone stray ambiguous even with singleton rescue.
    result = extract.extract_plus([REFUSED[0], "https://example.org/a", "https://example.org/b"], provider="tavily")
    assert result.get("error")
    assert result.get("refused_urls") == [REFUSED[0]]


@pytest.mark.parametrize("error", [TimeoutError("deadline"), RuntimeError("failure")])
def test_wrapper_failure_retains_refused_urls(monkeypatch, error):
    plugin = load_plugin("wsp_wrapper_refusal_test")
    engine = SimpleNamespace(_extract=extract, load_config=lambda: {})
    monkeypatch.setattr(plugin, "_load_search_module", lambda: engine)
    monkeypatch.setattr(plugin, "_call_with_timeout", Mock(side_effect=error))
    result = plugin._run_extract([REFUSED[0], "https://example.org/a"])
    assert result.get("refused_urls") == [REFUSED[0]]
