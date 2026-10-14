"""Selected provenance must describe the provider that actually supplied pages."""
from unittest.mock import Mock

import pytest

from plugin_loader import load_plugin
from test_extract_projection_golden import _env, _execute
from wsp_core import extract, providers
from wsp_core.compat_v3 import v3_response_to_legacy_extract


@pytest.mark.parametrize("first_contributes", [False, True])
@pytest.mark.parametrize("metadata", [False, True])
def test_stray_first_provider_does_not_own_fallback_payload(monkeypatch, first_contributes, metadata):
    urls = ["https://example.org/a", "https://example.org/b"]
    tavily = Mock(return_value={"provider": "tavily", "results": [
        {"url": urls[0] if first_contributes else "https://example.org/stray", "content": "real page"},
    ], **({"metadata": {"owner": "tavily"}} if metadata else {})})
    linkup = Mock(return_value={"provider": "linkup", "results": [
        {"url": url, "content": "real page"} for url in urls
    ], **({"metadata": {"owner": "linkup"}} if metadata else {})})
    monkeypatch.setattr(providers, "extract_tavily", tavily)
    monkeypatch.setattr(providers, "extract_linkup", linkup)
    with _env():
        execution = _execute(urls)
        payload = v3_response_to_legacy_extract(execution)
        cached = extract.extract_plus(urls, provider="tavily")
    # Unknown top-level metadata intentionally prevents lossy cache writes.
    if not metadata:
        assert cached.get("cached") is True
        assert tavily.call_count == linkup.call_count == 1
    for result in (payload, cached):
        assert result["provider"] == "linkup"
        if metadata:
            assert result["metadata"]["owner"] == "linkup"
        assert result["routing"]["provider"] == "linkup"
        assert result["routing"]["fallback_used"] is True
        assert all(item["content"] == "real page" for item in result["results"])
    assert execution.response.routing_receipt["selected_provider"] == "linkup"
    expected = {"tavily", "linkup"} if first_contributes else {"linkup"}
    assert {item["provider"] for item in execution.response.observations} == expected
    plugin = load_plugin("wsp_provenance_test")
    assert "[Provider: linkup]" in plugin._format_extract_results(payload)
