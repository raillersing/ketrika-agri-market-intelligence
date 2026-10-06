"""Sources registry loader and schema validator."""

import sys
from datetime import UTC
from pathlib import Path
from typing import Any

import yaml

from ketrika.core.models.source import SourceDefinition

REQUIRED_SOURCES = [
    "ocha_codab_mdg",
    "wfp_hdx_mdg",
    "wb_rtfp_mdg",
    "faostat",
    "nasa_power",
    "instat_nipc",
    "miasa_odr",
    "mincc_ppn",
    "douanes_stats",
]


def find_repo_root() -> Path:
    """Find repository root by looking for markers like .git or registry directory."""
    import os

    env_root = os.environ.get("KETRIKA_REPO_ROOT")
    if env_root:
        p = Path(env_root)
        if (p / "registry" / "sources.yaml").exists():
            return p

    candidates = [
        Path.cwd(),
        *Path.cwd().parents,
        Path("/workspace"),
        Path("/app"),
        Path("/"),
    ]
    for candidate in candidates:
        if (candidate / "registry" / "sources.yaml").exists():
            return candidate
    return Path.cwd()


def get_default_registry_path() -> Path:
    """Return default path to registry/sources.yaml."""
    root = find_repo_root()
    return root / "registry" / "sources.yaml"


def load_sources(registry_path: Path | str | None = None) -> list[SourceDefinition]:
    """Load and validate all source definitions from registry/sources.yaml."""
    path = Path(registry_path) if registry_path else get_default_registry_path()
    if not path.exists():
        raise FileNotFoundError(f"Source registry file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected YAML list in {path}, got {type(data).__name__}")

    sources: list[SourceDefinition] = []
    for item in data:
        sources.append(SourceDefinition.model_validate(item))
    return sources


def get_source(source_id: str, registry_path: Path | str | None = None) -> SourceDefinition:
    """Find a specific source by its unique ID."""
    sources = load_sources(registry_path)
    for s in sources:
        if s.source_id == source_id:
            return s
    raise KeyError(f"Source '{source_id}' not found in registry")


def validate_registry(
    registry_path: Path | str | None = None,
    check_fixtures: bool = True,
    check_docs: bool = True,
) -> list[str]:
    """Validate registry contents, schema compliance, fixtures and documentation."""
    errors: list[str] = []
    root = find_repo_root()
    path = Path(registry_path) if registry_path else get_default_registry_path()

    if not path.exists():
        return [f"Registry file does not exist: {path}"]

    try:
        sources = load_sources(path)
    except Exception as e:
        return [f"Failed to load or parse registry: {e}"]

    source_ids: set[str] = set()
    for s in sources:
        if s.source_id in source_ids:
            errors.append(f"Duplicate source_id: '{s.source_id}'")
        source_ids.add(s.source_id)

        # Prohibit direct PII
        if s.pii_class == "direct":
            errors.append(
                f"Source '{s.source_id}' has pii_class='direct' which is prohibited in MVP"
            )

        # Check documentation
        if check_docs:
            doc_file = root / "docs" / "sources" / f"{s.source_id}.md"
            if not doc_file.exists():
                errors.append(f"Missing documentation for '{s.source_id}': expected {doc_file}")

        # Check fixtures
        if check_fixtures:
            fixture_dirs = [
                root / "backend" / "tests" / "fixtures" / s.source_id,
                root / "registry" / "fixtures" / s.source_id,
            ]
            has_fixture = False
            for f_dir in fixture_dirs:
                if f_dir.exists() and any(f_dir.iterdir()):
                    has_fixture = True
                    break
            if not has_fixture:
                errors.append(
                    f"Missing fixture file for '{s.source_id}': expected in {fixture_dirs[0]} or {fixture_dirs[1]}"
                )

    # Check that all required MVP sources are present
    missing_required = set(REQUIRED_SOURCES) - source_ids
    if missing_required:
        errors.append(f"Missing required MVP sources in registry: {sorted(missing_required)}")

    return errors


def sync_sources_to_db(session: Any, registry_path: Path | str | None = None) -> int:
    """Synchronize source definitions from YAML registry into meta.source table.

    Returns the count of synced sources.
    """
    from datetime import datetime

    from sqlalchemy.dialects.postgresql import insert

    from ketrika.core.models.db import Source

    sources = load_sources(registry_path)
    count = 0
    now = datetime.now(UTC)

    for s in sources:
        spec_dict = s.model_dump(mode="json")
        stmt = (
            insert(Source)
            .values(
                source_id=s.source_id,
                spec=spec_dict,
                status=s.status,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[Source.source_id],
                set_={
                    "spec": spec_dict,
                    "status": s.status,
                    "updated_at": now,
                },
            )
        )
        session.execute(stmt)
        count += 1

    return count


def main() -> None:
    """CLI runner for ketrika validate-registry."""
    print("Ketrika Registry Validator")
    print("--------------------------")
    errors = validate_registry()
    if errors:
        print(f"Validation FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f"  [ERROR] {err}")
        sys.exit(1)
    else:
        sources = load_sources()
        print(f"Registry is valid! Successfully verified {len(sources)} sources:")
        for s in sources:
            print(f"  - {s.source_id}: {s.name} ({s.status}, {s.cadence})")
        sys.exit(0)


if __name__ == "__main__":
    main()
