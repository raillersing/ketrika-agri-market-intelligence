"""Fail-closed safety checks for local qualification, never production certification."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

import yaml

PROJECT = "ketrika-qualification"
DATABASE = "ketrika_qualification"
BUCKET = "ketrika-qa-bronze"
NETWORK = "ketrika_qualification_network"


class QualificationSafetyError(ValueError):
    """The requested destination is not explicitly isolated for testing."""


def validate_environment(environment: Mapping[str, str]) -> None:
    """Do not trust a flag alone: validate all mutation/notification targets."""
    required = {
        "APP_ENV": "test",
        "KETRIKA_QUALIFICATION": "1",
        "KETRIKA_DATASET_MODE": "test",
        "POSTGRES_DB": DATABASE,
        "POSTGRES_PASSWORD": "qa-local-only",
        "S3_BUCKET_BRONZE": BUCKET,
        "S3_ENDPOINT_URL": "http://minio:9000",
        "S3_ACCESS_KEY": "qualification-admin",
        "S3_SECRET_KEY": "qualification-local-only",
        "LLM_PROVIDER": "replay",
        "EXTERNAL_SEND_ENABLED": "0",
        "SMTP_HOST": "mailpit",
    }
    for key, expected in required.items():
        if environment.get(key) != expected:
            raise QualificationSafetyError(f"Unsafe or missing qualification setting: {key}")
    target = urlsplit(environment.get("DATABASE_URL", ""))
    if (
        target.scheme != "postgresql+psycopg"
        or target.hostname != "db"
        or target.port != 5432
        or target.path != f"/{DATABASE}"
        or target.username != "ketrika"
        or target.password != "qa-local-only"
    ):
        raise QualificationSafetyError("Database destination is not the dedicated test database")


def require_synthetic_test_database(host: str | None, database: str | None) -> None:
    """Synthetic seeding must also verify the actual bound SQLAlchemy session."""
    validate_environment(os.environ)
    if host != "db" or database != DATABASE:
        raise QualificationSafetyError("Synthetic data cannot be seeded into this bound session")


def validate_compose(document: str) -> None:
    """Reject published ports, ambient env files, foreign volumes and destinations."""
    spec = yaml.safe_load(document)
    if not isinstance(spec, dict) or spec.get("name") != PROJECT:
        raise QualificationSafetyError("Qualification project name must be fixed")
    networks = spec.get("networks", {})
    if not isinstance(networks, dict) or set(networks) != {"qualification"}:
        raise QualificationSafetyError("Only the qualification network is allowed")
    network = networks["qualification"]
    if (
        not isinstance(network, dict)
        or network.get("internal") is not True
        or network.get("name") != NETWORK
        or network.get("external")
    ):
        raise QualificationSafetyError("Qualification network must be internal and dedicated")
    volumes = spec.get("volumes", {})
    if not isinstance(volumes, dict) or not volumes:
        raise QualificationSafetyError("Dedicated named volumes are required")
    for volume in volumes.values():
        if (
            not isinstance(volume, dict)
            or not str(volume.get("name", "")).startswith("ketrika_qualification_")
            or volume.get("external")
            or volume.get("labels", {}).get("ketrika.scope") != "qualification"
        ):
            raise QualificationSafetyError("Foreign or unnamed volume is forbidden")
    services = spec.get("services", {})
    if not isinstance(services, dict) or set(services) != {
        "db",
        "minio",
        "minio-init",
        "mailpit",
        "api",
        "web",
        "browser",
    }:
        raise QualificationSafetyError("Unexpected qualification services")
    for name, service in services.items():
        if not isinstance(service, dict):
            raise QualificationSafetyError("Invalid qualification service")
        if (
            any(
                service.get(key)
                for key in ("ports", "env_file", "network_mode", "privileged", "cap_add")
            )
            or service.get("ipc") == "host"
        ):
            raise QualificationSafetyError(f"Unsafe network/environment privileges: {name}")
        if service.get("networks") != ["qualification"]:
            raise QualificationSafetyError(f"Non-isolated service network: {name}")
        for mount in service.get("volumes", []):
            if not isinstance(mount, str):
                raise QualificationSafetyError("Unsupported qualification mount format")
            source, _, _ = mount.partition(":")
            if source.startswith("."):
                if not mount.endswith(":ro"):
                    raise QualificationSafetyError("Host source must be mounted read-only")
            elif source not in volumes:
                raise QualificationSafetyError("Mount references a foreign volume")
    environment = services["api"].get("environment", {})
    if not isinstance(environment, dict):
        raise QualificationSafetyError("Qualification environment must be explicit")
    validate_environment({str(key): str(value) for key, value in environment.items()})
    if services["db"].get("environment", {}).get("POSTGRES_DB") != DATABASE:
        raise QualificationSafetyError("Database service is not dedicated")
    if services["db"].get("environment", {}).get("POSTGRES_PASSWORD") != "qa-local-only":
        raise QualificationSafetyError("Database account is not the public test account")
    minio_environment = services["minio"].get("environment", {})
    if minio_environment != {
        "MINIO_ROOT_USER": "qualification-admin",
        "MINIO_ROOT_PASSWORD": "qualification-local-only",
    }:
        raise QualificationSafetyError("Object storage account is not dedicated to qualification")


def validate_coverage(report: Mapping[str, object]) -> dict[str, float]:
    """Require at least eighty percent coverage for each prescribed package."""
    files = report.get("files")
    if not isinstance(files, dict):
        raise QualificationSafetyError("Coverage report is missing file details")
    results: dict[str, float] = {}
    for package in ("core", "extraction", "normalize"):
        covered = statements = 0
        for path, item in files.items():
            normalized = "/" + str(path).replace("\\", "/")
            if f"/ketrika/{package}/" not in normalized:
                continue
            summary = item["summary"]
            covered += int(summary["covered_lines"])
            statements += int(summary["num_statements"])
        if statements == 0:
            raise QualificationSafetyError(f"No measured coverage for {package}")
        percent = covered * 100 / statements
        results[package] = percent
        if percent < 80:
            raise QualificationSafetyError(f"Coverage below 80% for {package}: {percent:.2f}%")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("compose", "environment", "coverage"))
    parser.add_argument("path", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        if args.action == "environment":
            validate_environment(os.environ)
            result: object = {"isolated_test_environment": True}
        elif args.action == "compose":
            if args.path is None:
                raise QualificationSafetyError("Compose path is required")
            validate_compose(args.path.read_text())
            result = {"project": PROJECT, "network": "internal", "scope": "test infrastructure"}
        else:
            if args.path is None:
                raise QualificationSafetyError("Coverage report path is required")
            result = validate_coverage(json.loads(args.path.read_text()))
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        parser.exit(1, f"Qualification check failed: {exc}\n")
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
