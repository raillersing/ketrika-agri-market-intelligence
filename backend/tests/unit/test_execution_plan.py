"""Governance validation cannot silently accept missing or forged task states."""

from pathlib import Path

import pytest

from ketrika.core.execution_plan import (
    PlanValidationError,
    expand_dependencies,
    task_order,
    validate_documents,
)


def documents(dependency: str = "R0.1", priority: str = "MUST") -> tuple[str, str]:
    definitions = (
        "### R0.1 — First\n- **Priorité / dépendances :** MUST / aucune.\n"
        f"### R0.2 — Second\n- **Priorité / dépendances :** {priority} / {dependency}.\n"
    )
    rows = f"| R0.1 | MUST | IN_PROGRESS | — |\n| R0.2 | {priority} | TODO | — |\n"
    return definitions + rows, rows


def test_valid_plan_is_not_runtime_qualification() -> None:
    result = validate_documents(*documents())
    assert result["task_count"] == 2
    assert result["reverify_in_progress"] == ["R0.1"]
    assert result["ready_by_mandatory_dependencies"] == []
    assert "not runtime" in str(result["scope"])


def test_missing_status_never_defaults_to_todo() -> None:
    plan, progress = documents()
    with pytest.raises(PlanValidationError, match="missing"):
        validate_documents(plan, progress.splitlines()[0])


def test_mirror_must_match_canonical_progress() -> None:
    plan, progress = documents()
    with pytest.raises(PlanValidationError, match="mirror mismatch"):
        validate_documents(plan, progress.replace("IN_PROGRESS", "TODO"))


def test_duplicate_definition_is_rejected() -> None:
    plan, progress = documents()
    with pytest.raises(PlanValidationError, match="Duplicate task"):
        validate_documents(plan + "### R0.1 — Duplicate\n", progress)


def test_duplicate_status_is_rejected() -> None:
    plan, progress = documents()
    with pytest.raises(PlanValidationError, match="Duplicate status"):
        validate_documents(plan, progress + progress.splitlines()[0])


def test_empty_plan_fails() -> None:
    with pytest.raises(PlanValidationError, match="Empty"):
        validate_documents("", "")


def test_unknown_dependency_fails() -> None:
    with pytest.raises(PlanValidationError, match="Unknown dependency"):
        validate_documents(*documents("R9.9"))


def test_dependency_cycle_fails() -> None:
    plan, progress = documents()
    with pytest.raises(PlanValidationError, match="cycle"):
        validate_documents(plan.replace("MUST / aucune", "MUST / R0.2"), progress)


def test_must_cannot_require_optional_task() -> None:
    plan, progress = documents("R0.2")
    plan = plan.replace("MUST / aucune", "SHOULD / aucune").replace(
        "| R0.1 | MUST", "| R0.1 | SHOULD"
    )
    progress = progress.replace("| R0.1 | MUST", "| R0.1 | SHOULD")
    plan = plan.replace("MUST / R0.2", "MUST / R0.1")
    with pytest.raises(PlanValidationError, match="requires optional"):
        validate_documents(plan, progress)


@pytest.mark.parametrize("status", ["PARTIAL", "SUCCESS", "", "DONE-ish"])
def test_unknown_task_status_fails(status: str) -> None:
    plan, progress = documents()
    with pytest.raises(PlanValidationError, match="Invalid status"):
        validate_documents(plan, progress.replace("IN_PROGRESS", status))


def test_done_without_commit_proof_fails() -> None:
    plan, progress = documents()
    plan = plan.replace("IN_PROGRESS", "DONE")
    progress = progress.replace(
        "| R0.1 | MUST | IN_PROGRESS | — |",
        "| R0.1 | MUST | DONE | start | end | — | proof | — |",
    )
    with pytest.raises(PlanValidationError, match="verified commit"):
        validate_documents(plan, progress)


def test_done_with_incomplete_dependencies_fails() -> None:
    plan, progress = documents()
    with pytest.raises(PlanValidationError, match="Incomplete dependencies"):
        validate_documents(plan.replace("TODO", "DONE"), progress.replace("TODO", "DONE"))


def test_ranges_and_numeric_order() -> None:
    assert expand_dependencies("R1.9–R1.12") == {"R1.9", "R1.10", "R1.11", "R1.12"}
    assert task_order("R1.9") < task_order("R1.10")


@pytest.mark.parametrize("value", ["R1.4–R2.5", "R1.9–R1.2"])
def test_invalid_ranges_fail(value: str) -> None:
    with pytest.raises(PlanValidationError, match="Invalid dependency range"):
        expand_dependencies(value)


def test_actual_repository_plan_is_coherent() -> None:
    root = Path("/workspace")
    result = validate_documents(
        (root / "docs/plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md").read_text(),
        (root / "docs/plan/PROGRESS.md").read_text(),
    )
    assert result["task_count"] == 74
    assert result["priorities"] == {"MUST": 69, "SHOULD": 5}
