"""Qualification checks reject active destinations before any test mutation."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from ketrika.core.qualification import (
    QualificationSafetyError,
    main,
    require_synthetic_test_database,
    validate_compose,
    validate_coverage,
    validate_environment,
)


def compose_spec():
    return yaml.safe_load(Path("/workspace/docker-compose.qualification.yml").read_text())


def environment():
    return {
        key: str(value) for key, value in compose_spec()["services"]["api"]["environment"].items()
    }


def test_actual_profile_and_environment():
    validate_compose(yaml.safe_dump(compose_spec()))
    validate_environment(environment())


@pytest.mark.parametrize(
    "key",
    [
        "APP_ENV",
        "KETRIKA_QUALIFICATION",
        "KETRIKA_DATASET_MODE",
        "POSTGRES_DB",
        "S3_BUCKET_BRONZE",
        "S3_ENDPOINT_URL",
        "LLM_PROVIDER",
        "EXTERNAL_SEND_ENABLED",
        "SMTP_HOST",
    ],
)
def test_missing_safety_setting_is_rejected(key):
    settings = environment()
    del settings[key]
    with pytest.raises(QualificationSafetyError):
        validate_environment(settings)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://ketrika:fixture@db:5432/ketrika",
        "postgresql+psycopg://ketrika:fixture@localhost:5432/ketrika_qualification",
        "postgresql+psycopg://other:fixture@db:5432/ketrika_qualification",
        "postgresql+psycopg://ketrika:fixture@db:5434/ketrika_qualification",
        "sqlite:///ketrika_qualification",
        "",
    ],
)
def test_wrong_database_is_rejected(url):
    settings = environment()
    settings["DATABASE_URL"] = url
    with pytest.raises(QualificationSafetyError):
        validate_environment(settings)


def test_bound_session_is_checked(monkeypatch):
    for key, value in environment().items():
        monkeypatch.setenv(key, value)
    require_synthetic_test_database("db", "ketrika_qualification")
    for host, database in [("db", "ketrika"), ("localhost", "ketrika_qualification"), (None, None)]:
        with pytest.raises(QualificationSafetyError):
            require_synthetic_test_database(host, database)


@pytest.mark.parametrize("case", range(15))
def test_unsafe_compose_rejected(case):
    spec = deepcopy(compose_spec())
    if case == 0:
        spec["name"] = "aiagent"
    elif case == 1:
        spec["networks"] = {}
    elif case == 2:
        spec["networks"]["qualification"]["internal"] = False
    elif case == 3:
        spec["networks"]["qualification"]["external"] = True
    elif case == 4:
        spec["volumes"] = {}
    elif case == 5:
        next(iter(spec["volumes"].values()))["name"] = "active_bronze"
    elif case == 6:
        spec["services"]["api"]["ports"] = ["8090:8000"]
    elif case == 7:
        spec["services"]["api"]["env_file"] = [".env"]
    elif case == 8:
        spec["services"]["api"]["privileged"] = True
    elif case == 9:
        spec["services"]["api"]["networks"] = ["default"]
    elif case == 10:
        spec["services"]["api"]["volumes"] = ["./backend:/app"]
    elif case == 11:
        spec["services"]["api"]["volumes"] = ["foreign:/app"]
    elif case == 12:
        spec["services"]["api"]["volumes"] = [{"source": "foreign", "target": "/app"}]
    elif case == 13:
        spec["services"]["api"]["environment"] = []
    else:
        spec["services"]["db"]["environment"]["POSTGRES_DB"] = "ketrika"
    with pytest.raises(QualificationSafetyError):
        validate_compose(yaml.safe_dump(spec))


def coverage_report(covered=80):
    return {
        "files": {
            f"src/ketrika/{package}/module.py": {
                "summary": {"covered_lines": covered, "num_statements": 100}
            }
            for package in ("core", "extraction", "normalize")
        }
    }


def test_coverage_per_package():
    assert validate_coverage(coverage_report()) == {"core": 80, "extraction": 80, "normalize": 80}
    with pytest.raises(QualificationSafetyError, match="below 80"):
        validate_coverage(coverage_report(79))


@pytest.mark.parametrize("report", [{}, {"files": {}}, {"files": []}])
def test_missing_coverage_fails(report):
    with pytest.raises(QualificationSafetyError):
        validate_coverage(report)


def test_cli_environment(monkeypatch, capsys):
    for key, value in environment().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("sys.argv", ["qualification", "environment"])
    assert main() == 0
    assert "isolated_test_environment" in capsys.readouterr().out


@pytest.mark.parametrize("action", ["compose", "coverage"])
def test_cli_requires_path(action, monkeypatch):
    monkeypatch.setattr("sys.argv", ["qualification", action])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1


def test_cli_compose(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "qualification",
            "compose",
            "/workspace/docker-compose.qualification.yml",
        ],
    )
    assert main() == 0
    assert "test infrastructure" in capsys.readouterr().out


def test_cli_coverage(tmp_path, monkeypatch):
    import json

    report = tmp_path / "coverage.json"
    report.write_text(json.dumps(coverage_report()))
    monkeypatch.setattr("sys.argv", ["qualification", "coverage", str(report)])
    assert main() == 0
