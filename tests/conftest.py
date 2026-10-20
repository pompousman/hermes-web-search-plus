from wsp_core import extract
import os
import shutil
import socket
import sys

import pytest

from wsp_core import cache
from wsp_core import credentials
from wsp_core import provider_stats
from wsp_core import search
from wsp_core.config import keyless_public_env_var
from wsp_core.provider_registry import PROVIDER_SPECS


@pytest.fixture(autouse=True)
def _example_dns_fixture(monkeypatch):
    """Mock the example.com/example.org hosts used by mocked extraction tests.

    Keep URL/IP security validation enabled, without requiring live DNS. Safety
    tests can still replace getaddrinfo themselves to exercise private addresses,
    resolution errors and rebinding. All other hosts retain the real resolver.
    """
    resolve = socket.getaddrinfo

    def fixture_address(host, port, *args, **kwargs):
        if host in {"example.com", "example.org"}:
            host = "93.184.216.34"  # Public-address fixture, not a live DNS claim.
        return resolve(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fixture_address)


@pytest.fixture(autouse=True)
def _isolate_runtime_state(tmp_path, monkeypatch):
    """Keep mutable runtime state out of real paths and isolate every test.

    Search tests record outcomes for mocked providers; without isolation those
    samples would pollute the operator's provider_stats.json and, worse, feed
    back into routing decisions and make routing tests order-dependent.
    """
    monkeypatch.setattr(provider_stats, "PROVIDER_STATS_FILE", tmp_path / "provider_stats.json")
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(search, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(extract, "CACHE_DIR", tmp_path)


@pytest.fixture(autouse=True)
def _no_operator_credentials(monkeypatch):
    """Never let a test see the developer's real provider credentials.

    Without a host resolver wsp_core reads credentials from os.environ, so keys
    exported in the developer's shell would be seen. Routing depends on which
    providers are configured, so real keys changed routing decisions and sent
    a research fan-out to a provider the test had not mocked. A test that needs
    a key sets a dummy one itself. A resolver a test installs (as register()
    does under Hermes) is removed again afterwards.
    """
    for name, module in list(sys.modules.items()):
        if module is credentials or name.endswith(".wsp_core.credentials"):
            monkeypatch.setattr(module, "_resolver", None)
    for spec in PROVIDER_SPECS.values():
        monkeypatch.delenv(spec.env_var, raising=False)
        if spec.keyless:
            monkeypatch.delenv(keyless_public_env_var(spec.provider), raising=False)


@pytest.fixture(autouse=True)
def _no_legacy_env_files(request, monkeypatch):
    """Never let a real pre-5.1 ``.env`` next to the checkout change tool behaviour.

    5.1.3 looks for a leftover ``.env`` in the plugin directory and its parent and
    switches the tools into migration-message mode while no key is configured.
    A live install (or a developer's checkout) with such a file made dozens of
    unrelated tests fail. test_upgrade_ux_513.py builds its own plugin directory
    and tests the detection itself, so it keeps the real function.
    """
    if request.node.path.name == "test_upgrade_ux_513.py":
        return
    for module in list(sys.modules.values()):
        if hasattr(module, "_legacy_env_files") and hasattr(module, "_plugin_dir"):
            monkeypatch.setattr(module, "_legacy_env_files", lambda: [])


@pytest.fixture(autouse=True)
def _no_operator_donsetch(monkeypatch):
    """Never let a test find the developer's real DonSeTch binary.

    DonSeTch is resolved from DONSETCH_BIN or PATH. The real binary can start a
    local Chrome for browser-tier fetches, and setup/status tests probe it with
    ``donsetch --version`` - on a machine with DonSeTch installed every test
    run launched Chrome. Tests that need a binary pass an explicit path.
    """
    monkeypatch.delenv("DONSETCH_BIN", raising=False)
    real_which = shutil.which

    def which(cmd, *args, **kwargs):
        if os.path.basename(str(cmd)).lower().startswith("donsetch"):
            return None
        return real_which(cmd, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", which)


@pytest.fixture(autouse=True)
def _no_external_network(monkeypatch):
    """Fail any test that opens a real connection beyond loopback.

    Provider HTTP must be mocked. A test whose mock silently stops applying
    would otherwise reach the real provider with a fake key and still "pass"
    on the resulting error, so violations are recorded and failed at teardown
    even when the engine swallowed the exception.
    """
    real_connect = socket.socket.connect
    violations = []

    def guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if self.family == socket.AF_UNIX or (
            isinstance(host, str) and (host.startswith("127.") or host in {"::1", "localhost"})
        ):
            return real_connect(self, address, *args, **kwargs)
        violations.append(address)
        raise ConnectionRefusedError(f"test tried to open a real network connection to {address!r}")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    yield
    assert not violations, f"test opened real network connections: {violations}"


@pytest.fixture(autouse=True)
def _reset_secret_resolver():
    """A test that installs a credentials resolver must not leak it into the next test."""
    from wsp_core import credentials

    before = credentials.get_secret_resolver()
    yield
    credentials.set_secret_resolver(before)
