"""Dependency-free rescue diagnostics agree with YAML 1.1 scalar semantics."""
import sys
import types

import pytest

from plugin_loader import load_plugin

plugin = load_plugin("wsp_rescue_parser_511")


@pytest.mark.parametrize("scalar, expected", [("0", False), ("", False), ("false", False), ("'false'", True), ('"false"', True), ("off", False), ("NO", False), ("yes", True), ("true", True), ("null", False), ("~", False), ("1", True), ("''", False)])
@pytest.mark.parametrize("flow", [False, True])
@pytest.mark.parametrize("field", ["keyless_rescue", "keyless_fallback"])
def test_rescue_parsers_agree(monkeypatch, scalar, expected, flow, field):
    pytest.importorskip("yaml")
    text = (f"web: {{backend: wsp, {field}: {scalar}}}\n" if flow else f"web:\n  backend: wsp\n  {field}: {scalar}\n")
    parsed = plugin._keyless_rescue_state(text)
    monkeypatch.setitem(sys.modules, "yaml", None)
    fallback = plugin._keyless_rescue_state(text)
    assert parsed == fallback
    assert fallback["native_selected"] is True
    assert fallback["keyless_rescue"] is expected


def test_rescue_path_uses_active_profile_home(monkeypatch, tmp_path):
    constants = types.ModuleType("hermes_constants")
    constants.get_hermes_home = lambda: tmp_path / "profile"
    monkeypatch.setitem(sys.modules, "hermes_constants", constants)
    monkeypatch.delenv("HERMES_CONFIG", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "shared"))
    assert plugin._get_hermes_config_path() == tmp_path / "profile" / "config.yaml"
