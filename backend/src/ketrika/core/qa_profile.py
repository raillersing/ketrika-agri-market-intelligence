"""Read-only JUnit timing diagnostics, never test execution or qualification."""

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

MAX_BYTES = 16 * 1024 * 1024
MAX_CASES = 100_000


def _add(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 32
        return left + right


def profile_junit(path: Path, limit: int = 20) -> dict[str, Any]:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("qa_profile_invalid_limit")
    with path.open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError("qa_profile_report_too_large")
    decoded = content.decode("utf-8-sig")
    if "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
        raise ValueError("qa_profile_declarations_forbidden")
    root = ET.fromstring(decoded)
    if root.tag not in {"testsuite", "testsuites"}:
        raise ValueError("qa_profile_invalid_root")
    groups: dict[tuple[str, str], tuple[int, Decimal]] = {}
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    total = Decimal(0)
    for case in root.iter("testcase"):
        counts["tests"] += 1
        if counts["tests"] > MAX_CASES:
            raise ValueError("qa_profile_too_many_cases")
        try:
            seconds = Decimal(case.attrib["time"])
            if not seconds.is_finite() or seconds < 0 or seconds > Decimal("1000000000"):
                raise ValueError
            _, digits, exponent = seconds.as_tuple()
            if len(digits) > 16 or not isinstance(exponent, int) or not -6 <= exponent <= 9:
                raise ValueError
        except (KeyError, InvalidOperation, ValueError):
            raise ValueError("qa_profile_invalid_duration") from None
        # Names are generated test identifiers; never expose parameter payloads/logs.
        name = case.get("name", "").split("[", 1)[0]
        classname = case.get("classname", "")
        if not all(re.fullmatch(r"[A-Za-z0-9_.]{1,256}", part) for part in (classname, name)):
            raise ValueError("qa_profile_invalid_identifier")
        key = (classname, name)
        previous_count, previous_time = groups.get(key, (0, Decimal(0)))
        groups[key] = (previous_count + 1, _add(previous_time, seconds))
        total = _add(total, seconds)
        for tag in ("failure", "error", "skipped"):
            counts[{"failure": "failures", "error": "errors", "skipped": "skipped"}[tag]] += int(
                case.find(tag) is not None
            )
    if counts["tests"] == 0:
        raise ValueError("qa_profile_empty_report")
    ordered = sorted(groups.items(), key=lambda item: (-item[1][1], item[0]))
    return {
        "scope": "junit timing diagnostic only; not execution or qualification",
        "report_sha256": hashlib.sha256(content).hexdigest(),
        "counts": counts,
        "summed_testcase_seconds": str(total),
        "parameters_redacted": True,
        "slowest_groups": [
            {"classname": key[0], "name": key[1], "cases": value[0], "seconds": str(value[1])}
            for key, value in ordered[:limit]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    args = parser.parse_args()
    try:
        relative = Path(args.report)
        root = Path("/workspace").resolve()
        target = (root / relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(root) or target.suffix != ".xml":
            raise ValueError("qa_profile_invalid_path")
        result = profile_junit(target)
    except (OSError, ValueError, ET.ParseError):
        parser.exit(1, "QA profile refused: report missing, unsafe or invalid\n")
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
