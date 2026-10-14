"""Profile-owned endpoints and opt-ins cannot be inherited from shared config."""
import pytest

from wsp_core import config, credentials


@pytest.mark.parametrize("values, expected_url, expected_public", [
    ({"SEARXNG_INSTANCE_URL": "https://profile.example"}, "https://profile.example", False),
    ({}, None, False),
    ({"KEENABLE_ALLOW_PUBLIC": "false"}, None, False),
    ({"KEENABLE_ALLOW_PUBLIC": "true"}, None, True),
])
def test_profile_settings_override_shared_config(monkeypatch, values, expected_url, expected_public):
    monkeypatch.setattr(credentials, "_resolver", lambda name, default=None: values.get(name, default))
    monkeypatch.setattr(config, "_validate_searxng_url", lambda url: url)
    shared = {"searxng": {"base_url": "https://shared.example"}, "keenable": {"allow_public": True}}
    assert config.get_searxng_instance_url(shared) == expected_url
    assert config.keyless_public_allowed("keenable", shared) is expected_public


def test_standalone_settings_keep_file_precedence(monkeypatch):
    monkeypatch.setattr(credentials, "_resolver", None)
    monkeypatch.setattr(config, "_validate_searxng_url", lambda url: url)
    monkeypatch.setenv("SEARXNG_INSTANCE_URL", "https://environment.example")
    assert config.get_searxng_instance_url({"searxng": {"base_url": "https://file.example"}}) == "https://file.example"
    assert config.keyless_public_allowed("keenable", {"keenable": {"allow_public": True}})
