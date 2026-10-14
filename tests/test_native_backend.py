"""Portable adapter contracts; real Hermes discovery is tested separately."""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def backend(monkeypatch):
    abc = ModuleType("agent.web_search_provider")
    abc.WebSearchProvider = object
    web = ModuleType("hermes_cli.config")
    config = {"backend": "wsp"}
    web.load_config = lambda: {"web": config}
    monkeypatch.setitem(sys.modules, "agent.web_search_provider", abc)
    monkeypatch.setitem(sys.modules, "hermes_cli.config", web)
    spec = importlib.util.spec_from_file_location(
        "_wsp_native_unit", Path(__file__).resolve().parents[1] / "native_backend.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from wsp_core import extract

    engine = SimpleNamespace(
        _extract=extract,
        load_config=lambda: {"auto_routing": {}},
        provider_configured=lambda *args: True,
        SEARCH_PROVIDER_IDS=("fixture",), EXTRACT_PROVIDER_IDS=("fixture",),
        _provider_auto_allowed=lambda *args: True,
    )
    plugin = SimpleNamespace(
        _load_search_module=lambda: engine,
        _run_search=Mock(return_value={"provider": "fixture", "results": [
            {"url": "https://example.org", "title": "Source", "snippet": "Evidence"}]}),
        _run_extract=Mock(return_value={"results": [
            {"url": "https://example.org", "title": "Source", "content": "Evidence"}]}),
    )
    return SimpleNamespace(module=module, value=module.WSPNativeBackend(plugin),
                           plugin=plugin, config=config, engine=engine)


@pytest.mark.parametrize("web", [{"extract_backend": "wsp"}, None, [], "wsp"])
def test_web_config_uses_public_loader_and_always_returns_dict(backend, monkeypatch, web):
    config = ModuleType("hermes_cli.config")
    config.load_config = lambda: {"web": web}
    monkeypatch.setitem(sys.modules, "hermes_cli.config", config)
    assert backend.module._load_web_config() == (web if isinstance(web, dict) else {})
    config.load_config = Mock(side_effect=RuntimeError("unavailable"))
    assert backend.module._load_web_config() == {}


def test_no_implicit_selection(backend):
    backend.config.clear()
    assert not backend.value.is_available()
    assert not backend.value.supports_search()
    assert not backend.value.supports_extract()


def test_independent_pins(backend):
    backend.config.update(search_backend="searxng", extract_backend="wsp")
    assert not backend.value.supports_search()
    assert backend.value.supports_extract()
    assert backend.value.is_available()


@pytest.mark.parametrize("bad", [[], ["wsp"], 4, {}, True])
def test_malformed_config(backend, bad):
    backend.module._load_web_config = lambda: {"search_backend": bad}
    assert not backend.value.supports_search()


def test_requires_exact_plugin(backend):
    with pytest.raises(RuntimeError):
        backend.module.WSPNativeBackend()


def test_readiness_without_vendor_calls(backend):
    assert backend.value.is_available()
    backend.plugin._run_search.assert_not_called()
    backend.plugin._run_extract.assert_not_called()
    backend.engine.provider_configured = lambda *args: False
    assert not backend.value.is_available()


def test_readiness_honors_disabled_and_auto_allow(backend):
    backend.engine.load_config = lambda: {"auto_routing": {"disabled_providers": ["fixture"]}}
    assert not backend.value.is_available()
    backend.engine.load_config = lambda: {"auto_routing": {}}
    backend.engine._provider_auto_allowed = lambda *args: False
    assert not backend.value.is_available()


def test_readiness_ignores_blocked_searxng_url_when_another_provider_is_keyed(backend, monkeypatch):
    from wsp_core import config as wsp_config
    for spec in wsp_config.PROVIDER_SPECS.values():
        monkeypatch.delenv(spec.env_var, raising=False)
    monkeypatch.delenv("SEARXNG_ALLOW_PRIVATE", raising=False)
    config = {"auto_routing": {}, "searxng": {"instance_url": "http://127.0.0.1:8888"}}
    backend.engine.load_config = lambda: config
    backend.engine.provider_configured = wsp_config.provider_configured
    backend.engine.SEARCH_PROVIDER_IDS = ("searxng", "brave")
    backend.config.update(search_backend="wsp")
    assert not backend.value.is_available()  # only the blocked URL: nothing usable
    monkeypatch.setenv("BRAVE_API_KEY", "brave-test-key-1234567")
    assert backend.value.is_available()


@pytest.mark.parametrize("failure", ["missing", "raises"])
def test_no_subprocess_fallback(backend, failure):
    if failure == "missing":
        backend.plugin._load_search_module = lambda: None
    else:
        backend.plugin._load_search_module = Mock(side_effect=RuntimeError("private-data"))
    assert not backend.value.is_available()
    assert not backend.value.search("q")["success"]
    assert backend.value.extract(["https://example.org"])[0]["error"]
    backend.plugin._run_search.assert_not_called()
    backend.plugin._run_extract.assert_not_called()


def test_search_mapping_and_limit(backend):
    result = backend.value.search("q", 35)
    assert result["success"]
    assert result["data"]["web"][0]["description"] == "Evidence"
    assert result["metadata"]["effective_limit"] == 20
    assert backend.plugin._run_search.call_args.kwargs["count"] == 20


@pytest.mark.parametrize("payload", [None, {}, {"results": {}}, {"data": []}, {"data": None}, {"error": "secret-dummy"}])
def test_search_malformed_response(backend, payload):
    backend.plugin._run_search.return_value = payload
    result = backend.value.search("q")
    assert result["success"] is False
    assert "secret-dummy" not in str(result)


def test_legacy_search_shape(backend):
    backend.plugin._run_search.return_value = {"data": {"web": [
        {"url": "https://example.org", "description": "legacy"}]}}
    assert backend.value.search("q")["data"]["web"][0]["description"] == "legacy"


def test_exception_redaction(backend, caplog):
    backend.plugin._run_search.side_effect = RuntimeError("secret-dummy")
    backend.plugin._run_extract.side_effect = RuntimeError("secret-dummy")
    assert "secret-dummy" not in str(backend.value.search("q"))
    assert "secret-dummy" not in str(backend.value.extract(["https://example.org"]))
    assert "secret-dummy" not in caplog.text


def test_extract_association_and_missing_failures(backend):
    backend.plugin._run_extract.return_value = {"results": [
        {"url": "https://foreign.invalid", "content": "foreign"},
        {"url": "https://example.org/second", "content": "second"},
        {"url": "https://example.org", "error": "secret-dummy"},
    ]}
    urls = ["https://example.org", "https://example.org/missing", "https://example.org/second"]
    result = backend.value.extract(urls)
    assert [r["url"] for r in result] == urls
    assert result[0]["error"] and result[1]["error"]
    assert result[2]["content"] == "second"
    assert "foreign" not in str(result) and "secret-dummy" not in str(result)


def test_extract_format_metadata(backend):
    backend.plugin._run_extract.return_value = {"results": [
        {"url": "https://example.org", "markdown": "text", "truncated": True}]}
    row = backend.value.extract(["https://example.org"], format="html")[0]
    assert row["content"] == "text" and row["metadata"]["truncated"]
    assert backend.plugin._run_extract.call_args.kwargs["output_format"] == "html"


def test_registration_and_older_host(backend):
    handle = object()
    ctx = SimpleNamespace(register_web_search_provider=Mock(return_value=handle))
    assert backend.module.register_native_backend(ctx, backend.plugin) is handle
    registered = ctx.register_web_search_provider.call_args.args[0]
    assert registered.plugin is backend.plugin
    assert backend.module.register_native_backend(object(), backend.plugin) is None
    ctx.register_web_search_provider.side_effect = RuntimeError("failure")
    assert backend.module.register_native_backend(ctx, backend.plugin) is None


def _refused(row):
    marker = row.get("blocked_by_policy")
    return bool(marker) and "error" in row and not row.get("content")


def test_extract_refused_url_carries_hermes_policy_marker_all_refused(backend):
    # Whole-batch refusal: the engine returns a joined error and no rows.
    backend.plugin._run_extract.return_value = {
        "provider": "auto", "results": [],
        "error": "Extraction URL blocked: 127.0.0.1 is private/internal",
    }
    urls = ["http://127.0.0.1/admin", "http://10.0.0.5/x"]
    rows = backend.value.extract(urls)
    assert [r["url"] for r in rows] == urls
    assert all(_refused(r) for r in rows)
    assert rows[0]["blocked_by_policy"]["host"] == "127.0.0.1"
    assert "10.0.0.5" not in rows[0]["error"]


def test_extract_refused_url_in_mixed_batch_is_marked_only_for_that_url(backend):
    backend.plugin._run_extract.return_value = {"results": [
        {"url": "https://example.org", "content": "ok"},
        {"url": "http://localhost/", "title": "", "content": "",
         "error": "Extraction URL blocked: localhost is private/internal"},
        {"url": "https://example.org/down", "content": "", "error": "provider boom"},
    ]}
    rows = backend.value.extract(["https://example.org", "http://localhost/", "https://example.org/down"])
    assert "blocked_by_policy" not in rows[0] and rows[0]["content"] == "ok"
    assert _refused(rows[1])
    # An ordinary provider failure must stay rescuable: no policy marker.
    assert rows[2]["error"] and "blocked_by_policy" not in rows[2]


def test_extract_ordinary_failures_never_get_policy_marker(backend):
    # Only valid public URLs are rescuable. Invalid/non-HTTP input must not
    # be forwarded to third-party rescue backends either.
    for payload in (
        {"results": [], "error": "All extraction providers failed"},
        {"results": [{"url": "https://example.org", "error": "timeout"}]},
    ):
        backend.plugin._run_extract.return_value = payload
        assert all("blocked_by_policy" not in r for r in backend.value.extract(["https://example.org"]))
    backend.plugin._run_extract.side_effect = RuntimeError("boom")
    assert all("blocked_by_policy" not in r for r in backend.value.extract(["https://example.org"]))


def test_real_engine_private_url_returns_policy_marker(monkeypatch):
    """End to end through the real plugin and engine: literal private IP, no network."""
    from plugin_loader import load_plugin

    plugin = load_plugin("wsp_plugin_native_rescue_under_test")
    abc = ModuleType("agent.web_search_provider")
    abc.WebSearchProvider = object
    web = ModuleType("hermes_cli.config")
    web.load_config = lambda: {"web": {"backend": "wsp"}}
    monkeypatch.setitem(sys.modules, "agent.web_search_provider", abc)
    monkeypatch.setitem(sys.modules, "hermes_cli.config", web)
    spec = importlib.util.spec_from_file_location(
        "_wsp_native_real", Path(__file__).resolve().parents[1] / "native_backend.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = module.WSPNativeBackend(plugin).extract(["http://127.0.0.1:8080/secret", "http://192.168.1.10/"])
    assert len(rows) == 2 and all(r.get("blocked_by_policy") for r in rows)
