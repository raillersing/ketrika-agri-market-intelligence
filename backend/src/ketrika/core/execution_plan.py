"""Read-only validation of the normative plan and its progress/status mirror."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

TASK_ID = re.compile(r"R\d+\.\d+\Z")
STATUSES = frozenset({"TODO", "IN_PROGRESS", "DONE", "BLOCKED"})
PRIORITIES = frozenset({"MUST", "SHOULD", "COULD"})
RANGE = re.compile(r"(R\d+)\.(\d+)–(?:(R\d+)\.)?(\d+)")


class PlanValidationError(ValueError):
    """The plan is unsafe or its execution state cannot be trusted."""


@dataclass(frozen=True)
class Task:
    task_id: str
    priority: str
    dependencies: frozenset[str]
    condition: str


@dataclass(frozen=True)
class TaskState:
    priority: str
    status: str
    columns: tuple[str, ...]


def expand_dependencies(value: str) -> frozenset[str]:
    """Expand same-phase ranges; conditional requirements are kept separately."""

    def expand(match: re.Match[str]) -> str:
        phase, start, end_phase, end = match.groups()
        if (end_phase and end_phase != phase) or int(end) < int(start):
            raise PlanValidationError(f"Invalid dependency range: {match.group()}")
        return ", ".join(f"{phase}.{index}" for index in range(int(start), int(end) + 1))

    return frozenset(re.findall(r"\bR\d+\.\d+\b", RANGE.sub(expand, value)))


def read_tasks(document: str) -> dict[str, Task]:
    """Read task definitions, not the status table or explanatory examples."""
    headings = list(re.finditer(r"(?m)^### (R\d+\.\d+) — .+$", document))
    tasks: dict[str, Task] = {}
    for index, heading in enumerate(headings):
        task_id = heading.group(1)
        if task_id in tasks:
            raise PlanValidationError(f"Duplicate task: {task_id}")
        end = headings[index + 1].start() if index + 1 < len(headings) else len(document)
        block = document[heading.end() : end]
        metadata = re.search(
            r"(?m)^- \*\*Priorité / dépendances :\*\* (MUST|SHOULD|COULD) / (.+)$", block
        )
        if metadata is None:
            raise PlanValidationError(f"Missing task metadata: {task_id}")
        required, _, condition = metadata.group(2).partition(";")
        tasks[task_id] = Task(
            task_id, metadata.group(1), expand_dependencies(required), condition.strip()
        )
    if not tasks:
        raise PlanValidationError("Empty execution plan")
    return tasks


def read_states(document: str) -> dict[str, TaskState]:
    """Read explicit R rows; absent or unknown states never default to TODO."""
    states: dict[str, TaskState] = {}
    for line in document.splitlines():
        if not line.startswith("|"):
            continue
        columns = tuple(value.strip().strip("*") for value in line.strip("|").split("|"))
        if not columns or TASK_ID.fullmatch(columns[0]) is None:
            continue
        task_id = columns[0]
        if task_id in states:
            raise PlanValidationError(f"Duplicate status: {task_id}")
        if len(columns) < 3 or columns[1] not in PRIORITIES or columns[2] not in STATUSES:
            raise PlanValidationError(f"Invalid status/priority row: {task_id}")
        states[task_id] = TaskState(columns[1], columns[2], columns)
    return states


def task_order(task_id: str) -> tuple[int, int]:
    phase, index = task_id[1:].split(".")
    return int(phase), int(index)


def validate_documents(plan: str, progress: str) -> dict[str, object]:
    """Validate graph, mandatory dependencies, states and completed-task evidence."""
    tasks = read_tasks(plan)
    mirror = read_states(plan)
    states = read_states(progress)
    for label, entries in (("progress", states), ("plan mirror", mirror)):
        if entries.keys() != tasks.keys():
            missing = sorted(tasks.keys() - entries.keys(), key=task_order)
            unknown = sorted(entries.keys() - tasks.keys(), key=task_order)
            raise PlanValidationError(f"{label}: missing={missing}, unknown={unknown}")

    visits: dict[str, int] = {}

    def visit(task_id: str) -> None:
        if visits.get(task_id) == 1:
            raise PlanValidationError(f"Dependency cycle at {task_id}")
        if visits.get(task_id) == 2:
            return
        visits[task_id] = 1
        for dependency in tasks[task_id].dependencies:
            if dependency not in tasks:
                raise PlanValidationError(f"Unknown dependency {dependency} for {task_id}")
            if tasks[task_id].priority == "MUST" and tasks[dependency].priority != "MUST":
                raise PlanValidationError(f"MUST {task_id} requires optional {dependency}")
            visit(dependency)
        visits[task_id] = 2

    for task_id, task in tasks.items():
        visit(task_id)
        state = states[task_id]
        if state.priority != task.priority or mirror[task_id].priority != task.priority:
            raise PlanValidationError(f"Priority mismatch: {task_id}")
        if state.status != mirror[task_id].status:
            raise PlanValidationError(f"Status mirror mismatch: {task_id}")
        if state.status == "DONE":
            if any(states[dependency].status != "DONE" for dependency in task.dependencies):
                raise PlanValidationError(f"Incomplete dependencies for DONE {task_id}")
            if len(state.columns) != 8:
                raise PlanValidationError(f"Missing completion fields: {task_id}")
            if not re.fullmatch(r"[0-9a-f]{7,40}", state.columns[5]):
                raise PlanValidationError(f"Missing verified commit for DONE {task_id}")
            if state.columns[6] in {"", "—"} or state.columns[4] in {"", "—"}:
                raise PlanValidationError(f"Missing evidence/end time for DONE {task_id}")

    resumable = sorted(
        (task_id for task_id, state in states.items() if state.status == "IN_PROGRESS"),
        key=task_order,
    )
    candidates = [
        task
        for task in tasks.values()
        if states[task.task_id].status == "TODO"
        and all(states[dependency].status == "DONE" for dependency in task.dependencies)
    ]
    candidates.sort(
        key=lambda task: (tuple(PRIORITIES_ORDER).index(task.priority), task_order(task.task_id))
    )
    return {
        "task_count": len(tasks),
        "priorities": dict(Counter(task.priority for task in tasks.values())),
        "statuses": dict(Counter(state.status for state in states.values())),
        "reverify_in_progress": resumable,
        "ready_by_mandatory_dependencies": [task.task_id for task in candidates],
        "conditions_to_verify": {
            task.task_id: task.condition for task in candidates if task.condition
        },
        "scope": "documentary consistency, not runtime/source/model qualification",
    }


PRIORITIES_ORDER = ("MUST", "SHOULD", "COULD")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/workspace"))
    args = parser.parse_args()
    try:
        result = validate_documents(
            (args.root / "docs/plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md").read_text(),
            (args.root / "docs/plan/PROGRESS.md").read_text(),
        )
    except (OSError, PlanValidationError) as exc:
        parser.exit(1, f"Governance validation failed: {exc}\n")
    # CLI report, not debugging: machine-readable and contains no secrets.
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
