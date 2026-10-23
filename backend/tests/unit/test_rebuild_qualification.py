"""Fail-closed offline destination checks; mocks are not a real SQL replay receipt."""

import hashlib
import re
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from ketrika.core.bronze import BronzeStore
from ketrika.core.rebuild_bronze import LocalBronzeClient, LocalBronzeError
from ketrika.core.rebuild_manifest import OBS_COLUMNS
from ketrika.pipelines.rebuild_qualification import (
    DATABASE,
    SOCKET,
    RebuildSafetyError,
    bronze_inventory_fingerprint,
    compare_versioned_recompute,
    require_business_baseline,
    require_destination,
    require_network_none,
    versioned_recompute_receipt,
)


@pytest.mark.parametrize("business_count", [0, 1])
def test_replay_requires_nonempty_business_baseline_not_just_metadata(business_count):
    manifest = {"tables": {table: {"count": business_count} for table in OBS_COLUMNS}}
    if business_count:
        require_business_baseline(manifest)
    else:
        with pytest.raises(RebuildSafetyError, match="business_baseline_empty"):
            require_business_baseline(manifest)


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


def test_recompute_refuses_active_destination_before_read_or_write(monkeypatch):
    monkeypatch.setattr("ketrika.pipelines.rebuild_qualification.require_network_none", lambda: {})
    session = FakeSession(URL.replace(DATABASE, "ketrika"))
    with pytest.raises(RebuildSafetyError, match="destination_not_dedicated"):
        versioned_recompute_receipt(session)
    assert session.statements == []


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


DIGEST_A = hashlib.sha256(b"rice").hexdigest()
DIGEST_B = hashlib.sha256(b"{}").hexdigest()


def local_store(tmp_path, objects):
    for digest, content in ((DIGEST_A, b"rice"), (DIGEST_B, b"{}")):
        path = tmp_path / (digest + ".blob")
        if not path.exists():
            path.write_bytes(content)
    return BronzeStore(
        bucket_name="synthetic-offline-copy",
        client=LocalBronzeClient(tmp_path, "synthetic-offline-copy", objects),
    )


def test_bronze_inventory_fingerprint_order_insensitive(tmp_path):
    objects = {
        "source/blob.csv": {"sha256": DIGEST_A, "size_bytes": 4},
        "source/study.json": {"sha256": DIGEST_B, "size_bytes": 2},
    }
    first = bronze_inventory_fingerprint(local_store(tmp_path, objects))
    reversed_store = local_store(tmp_path, dict(reversed(list(objects.items()))))
    assert first == bronze_inventory_fingerprint(reversed_store)
    assert first["count"] == 2
    assert re.fullmatch("[0-9a-f]{64}", first["sha256"]) is not None


def test_bronze_inventory_fingerprint_changes_when_descriptor_changes(tmp_path):
    objects = {"source/blob.csv": {"sha256": DIGEST_A, "size_bytes": 4}}
    different = {
        "source/blob.csv": {"sha256": DIGEST_A, "size_bytes": 4},
        "source/study.json": {"sha256": DIGEST_B, "size_bytes": 2},
    }
    assert bronze_inventory_fingerprint(
        local_store(tmp_path, objects)
    ) != bronze_inventory_fingerprint(local_store(tmp_path, different))


def test_non_local_bronze_client_refused_for_inventory_fingerprint():
    with pytest.raises(RebuildSafetyError, match="requires_local_bronze_copy"):
        bronze_inventory_fingerprint(BronzeStore(bucket_name="bucket", client=SimpleNamespace()))


@pytest.mark.parametrize("mutation", ["same_size", "truncated", "missing"])
def test_inventory_rereads_bytes_even_when_descriptors_are_unchanged(tmp_path, mutation):
    store = local_store(tmp_path, {"rice": {"sha256": DIGEST_A, "size_bytes": 4}})
    assert bronze_inventory_fingerprint(store)["count"] == 1
    path = tmp_path / (DIGEST_A + ".blob")
    if mutation == "missing":
        path.unlink()
    else:
        path.write_bytes(b"corn" if mutation == "same_size" else b"r")
    with pytest.raises(LocalBronzeError):
        bronze_inventory_fingerprint(store)


def test_versioned_recompute_comparison_excludes_only_documented_technical():
    run_one = {"n_series": 1, "forecasts_generated": 3, "model_run_id": "aaa11111"}
    run_two = {"n_series": 1, "forecasts_generated": 3, "model_run_id": "bbb22222"}
    assert compare_versioned_recompute(run_one, run_two, ((), ()), ([], []))


def test_versioned_recompute_comparison_detects_business_divergence():
    run_one = {"n_series": 1, "forecasts_generated": 3, "model_run_id": "aaa11111"}
    run_two = {"n_series": 1, "forecasts_generated": 3, "model_run_id": "aaa11111"}
    assert not compare_versioned_recompute(run_one, {"n_series": 2}, ((), ()), ([], []))
    assert not compare_versioned_recompute(run_one, run_two, ((1,), (2,)), ([], []))


def test_versioned_recompute_comparison_accepts_abstained_runs():
    run_one = {"status": "abstained", "reason": "no_eligible_series", "n_series": 0}
    run_two = {"status": "abstained", "reason": "no_eligible_series", "n_series": 0}
    assert compare_versioned_recompute(run_one, run_two, ((), ()), ([], []))
