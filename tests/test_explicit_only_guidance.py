"""5.1.4: a configured explicit-only provider (e.g. DonSeTch) is named, not reported as missing.

Seen live: with DonSeTch as the only provider, an automatic search answered
"No configured search provider is available … Missing API key for serper", and
the model told the user DonSeTch was not set up.
"""
from wsp_core import config as wsp_config


def _guidance(capability, candidates, config=None, requested="auto"):
    payload = {"error": "All providers failed"}
    wsp_config.add_provider_setup_guidance(payload, capability, candidates, config or {}, requested_provider=requested)
    return payload


def test_configured_donsetch_is_named_with_both_ways_to_use_it(monkeypatch):
    monkeypatch.setenv("DONSETCH_BIN", "/opt/donsetch/bin/donsetch")
    payload = _guidance("search", ["serper", "brave", "tavily"])
    assert payload["error_type"] == "explicit_only_provider_configured"
    assert "DonSeTch (local MCP) is set up but only runs when asked for" in payload["error"]
    assert 'provider="donsetch"' in payload["error"]
    assert "hermes web-search-plus config set-auto-allow donsetch on" in payload["error"]
    assert payload["explicit_only_providers"] == ["donsetch"]
    assert "Missing API key" not in payload["error"]


def test_extract_wording(monkeypatch):
    monkeypatch.setenv("DONSETCH_BIN", "/opt/donsetch/bin/donsetch")
    payload = _guidance("extract", ["tavily", "exa"])
    assert payload["error"].startswith("No provider for automatic extraction is configured.")


def test_nothing_configured_keeps_the_setup_hint():
    payload = _guidance("search", ["serper", "brave", "tavily"])
    assert payload["error_type"] == "provider_setup_required"
    assert "hermes web-search-plus setup --preset starter" in payload["error"]


def test_auto_allowed_donsetch_is_not_reported_as_explicit_only(monkeypatch):
    monkeypatch.setenv("DONSETCH_BIN", "/opt/donsetch/bin/donsetch")
    config = {"auto_routing": {"auto_allow": {"donsetch": True}}}
    payload = _guidance("search", ["serper", "brave"], config)
    assert payload.get("error_type") != "explicit_only_provider_configured"


def test_explicit_request_for_an_unconfigured_provider_is_unchanged(monkeypatch):
    monkeypatch.setenv("DONSETCH_BIN", "/opt/donsetch/bin/donsetch")
    payload = _guidance("search", ["serper"], requested="serper")
    assert payload["error_type"] == "requested_provider_not_configured"
