"""web_extract_plus normalises provider names like the search tool does."""
import os
from unittest import mock

import pytest

from plugin_loader import load_plugin
from wsp_core import extract

plugin = load_plugin("wsp_plugin_test_extract_provider_names")

TAVILY_RESULT = {"provider": "tavily", "results": [{"url": "https://example.com", "content": "tavily page"}]}


@pytest.fixture()
def extract_handler():
    registered = {}

    class Ctx:
        def register_tool(self, **kwargs):
            registered[kwargs["name"]] = kwargs

    plugin.register(Ctx())
    return registered["web_extract_plus"]["handler"]


@pytest.mark.parametrize("value", ["Tavily", " tavily ", "TAVILY"])
def test_tool_accepts_provider_in_any_case_or_with_spaces(extract_handler, value):
    with mock.patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}, clear=True):
        with mock.patch("wsp_core.providers.extract_tavily", return_value=TAVILY_RESULT) as mock_tavily:
            output = extract_handler({"urls": ["https://example.com"], "provider": value})

    mock_tavily.assert_called_once()
    assert "[Provider: tavily]" in output
    assert "tavily page" in output


@pytest.mark.parametrize("value", ["Tavily", " tavily ", "TAVILY"])
def test_extract_plus_accepts_provider_in_any_case_or_with_spaces(value):
    with mock.patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}, clear=True):
        with mock.patch("wsp_core.providers.extract_tavily", return_value=TAVILY_RESULT) as mock_tavily:
            result = extract.extract_plus(["https://example.com"], provider=value)

    mock_tavily.assert_called_once()
    assert result["provider"] == "tavily"
    assert "error" not in result


@pytest.mark.parametrize("value", ["brave", "nope"])
def test_tool_unknown_or_search_only_provider_gives_clean_error(extract_handler, value):
    with mock.patch.object(plugin, "_run_extract", side_effect=AssertionError("must not extract")):
        output = extract_handler({"urls": ["https://example.com"], "provider": value})

    assert output.startswith("Extract error: unknown provider ")
    assert "Valid providers:" in output
    assert "tavily" in output


@pytest.mark.parametrize("value", ["brave", "nope"])
def test_extract_plus_unknown_or_search_only_provider_gives_clean_error(value):
    with mock.patch("wsp_core.providers.extract_tavily", side_effect=AssertionError("must not call")):
        result = extract.extract_plus(["https://example.com"], provider=value)

    assert result["results"] == []
    assert "unknown extraction provider" in result["error"]
    assert "tavily" in result["error"]
