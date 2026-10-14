"""Only an absent scope module may enable legacy credential reads."""
import builtins

import pytest

from plugin_loader import load_plugin
from wsp_core import config, credentials

plugin = load_plugin("wsp_resolver_fail_closed_511")


@pytest.mark.parametrize("error", [ImportError("broken import"), ModuleNotFoundError("missing dependency", name="scope_dependency"), RuntimeError("scope initialization failed")])
def test_broken_scope_import_fails_closed(monkeypatch, caplog, error):
    real_import = builtins.__import__

    def importing(name, *args, **kwargs):
        if name == "agent.secret_scope":
            raise error
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importing)
    monkeypatch.setenv("BRAVE_API_KEY", "process-fixture-credential")
    with caplog.at_level("WARNING"):
        plugin._install_hermes_secret_resolver()
    assert not credentials.file_credentials_allowed()
    assert "WARNING" in caplog.text and "disabled" in caplog.text
    with pytest.raises(RuntimeError, match="unavailable") as caught:
        config.get_api_key("brave", {"brave": {"api_key": "file-fixture-credential"}})
    assert credentials.is_secret_scope_error(caught.value)


@pytest.mark.parametrize("missing", ["agent", "agent.secret_scope"])
def test_absent_scope_module_allows_legacy_host(monkeypatch, missing):
    real_import = builtins.__import__

    def importing(name, *args, **kwargs):
        if name == "agent.secret_scope":
            raise ModuleNotFoundError("old host", name=missing)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importing)
    plugin._install_hermes_secret_resolver()
    assert credentials.file_credentials_allowed()
