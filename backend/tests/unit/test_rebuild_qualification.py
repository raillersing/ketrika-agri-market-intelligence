"""Fail-closed offline destination checks; mocks are not a real SQL replay receipt."""

from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from ketrika.pipelines.rebuild_qualification import (
    DATABASE,
    SOCKET,
    RebuildSafetyError,
    require_destination,
    require_network_none,
)

URL = f"postgresql+psycopg://ketrika:qa-local-only@/{DATABASE}?host={SOCKET}"


class FakeSession:
    def __init__(self, url=URL, actual=(DATABASE, None)):
        self.url, self.actual = make_url(url), actual
        self.statements = []

    def get_bind(self):
        return SimpleNamespace(engine=SimpleNamespace(url=self.url))

    def execute(self, statement):
        self.statements.append(str(statement))
        return SimpleNamespace(one=lambda: self.actual)


def test_dedicated_socket_and_bound_database_required():
    session = FakeSession()
    require_destination(session)
    assert session.statements == ["SELECT current_database(), inet_server_addr()"]


@pytest.mark.parametrize(
    "url",
    [
        URL.replace(DATABASE, "ketrika"),
        URL.replace(DATABASE, "ketrika_qualification"),
        URL.replace("@/", "@db/"),
        URL.replace("@/", "@localhost:5432/"),
        URL.replace("ketrika:", "postgres:"),
        URL.replace("qa-local-only", "private-secret-value"),
        URL.replace(SOCKET, "/var/run/postgresql"),
        URL + "&port=5432",
        URL.replace("postgresql+psycopg", "postgresql"),
    ],
)
def test_unsafe_url_refused_before_any_query(url):
    session = FakeSession(url)
    with pytest.raises(RebuildSafetyError, match="destination_not_dedicated") as error:
        require_destination(session)
    assert session.statements == []
    assert "private-secret-value" not in str(error.value)


@pytest.mark.parametrize("actual", [("ketrika", None), (DATABASE, "127.0.0.1")])
def test_actual_bound_server_checked(actual):
    session = FakeSession(actual=actual)
    with pytest.raises(RebuildSafetyError, match="bound_destination_mismatch"):
        require_destination(session)
    assert all(statement.startswith("SELECT ") for statement in session.statements)


def test_network_none_kernel_observations(tmp_path):
    interfaces = tmp_path / "net"
    interfaces.mkdir()
    (interfaces / "lo").mkdir()
    routes = tmp_path / "route"
    routes.write_text("Iface\tDestination\tGateway\n")
    assert require_network_none(interfaces, routes) == {
        "interfaces": ["lo"],
        "external_ipv4_routes": 0,
    }
    (interfaces / "eth0").mkdir()
    with pytest.raises(RebuildSafetyError, match="network_not_isolated"):
        require_network_none(interfaces, routes)


def test_external_route_refused_even_with_forged_interface_inventory(tmp_path):
    interfaces = tmp_path / "net"
    interfaces.mkdir()
    (interfaces / "lo").mkdir()
    routes = tmp_path / "route"
    routes.write_text("Iface\tDestination\tGateway\neth0\t00000000\t01020304\n")
    with pytest.raises(RebuildSafetyError, match="external_route_present"):
        require_network_none(interfaces, routes)


@pytest.mark.parametrize("header", ["", "unexpected\n"])
def test_missing_or_invalid_kernel_evidence_refused(tmp_path, header):
    interfaces = tmp_path / "net"
    interfaces.mkdir()
    (interfaces / "lo").mkdir()
    routes = tmp_path / "route"
    routes.write_text(header)
    with pytest.raises(RebuildSafetyError):
        require_network_none(interfaces, routes)
    with pytest.raises(RebuildSafetyError, match="evidence_unreadable"):
        require_network_none(interfaces, tmp_path / "missing")
