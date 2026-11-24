"""Measured offline qualification; no seed, restore, SQL execution or network."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ketrika.core import qualification_metrics as metrics
from ketrika.core.corpus import load_manifest, validate_manifest
from ketrika.core.external_corpus import inspect_packet
from ketrika.core.external_replay import PRODUCER, verify_external_replay
from ketrika.core.qualification import QualificationSafetyError
from ketrika.core.qualification_reports import (
    ENVIRONMENT_IDENTITY,
    e2e_counts,
    evidence_path,
    frontend_counts,
    junit_counts,
    load_json_report,
    native_environment,
    source_fingerprint,
)
from ketrika.core.registry import load_sources

CRITERIA = {
    "provenance": ("100 % source-cell vérifiés", "provenance"),
    "sources": ("9/9 MUST qualifiées, planned/disabled exclus", "sources"),
    "parsing": (">=99 % par run actif", "runs"),
    "golden": (">=99 % par champ ODR et MinCC", "golden"),
    "llm_gold": ("0 valeur LLM non vérifiée", "provenance"),
    "rebuild": ("0 différence de comptes ET contenu, 0 réseau", "rebuild"),
    "forecasts": (">=10 séries avec prévision/backtest", "forecasts"),
    "api": ("P95 <1000 ms, >=200 requêtes par endpoint", "api"),
    "copilot": (">=80 %, 0 requête interdite", "copilot"),
    "bulletin": ("0 chiffre non référencé", "bulletin"),
    "backend": ("100 % cas collectés verts, non vide", "backend_junit"),
    "frontend": ("100 % cas verts, quatre étapes complètes", "frontend_receipt"),
    "e2e": ("100 % cas collectés verts, non vide", "e2e_junit"),
    "corpus": ("corpus authentique, annotations vérifiées non vides", "corpus"),
}
R0_REQUIRED = {"backend", "frontend", "e2e", "corpus", "provenance", "rebuild"}
KNOWN_EVIDENCE = {
    "provenance",
    "sources",
    "runs",
    "golden",
    "rebuild",
    "forecasts",
    "api",
    "copilot",
    "bulletin",
    "backend_junit",
    "backend_inventory",
    "frontend_receipt",
    "frontend_vitest",
    "e2e_junit",
    "e2e_inventory",
    "e2e_receipt",
    "corpus",
}


def utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise QualificationSafetyError("evidence_date_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise QualificationSafetyError("evidence_date_invalid") from None
    offset = parsed.utcoffset()
    if parsed.tzinfo is None or offset is None or offset.total_seconds() != 0:
        raise QualificationSafetyError("evidence_date_not_utc")
    return parsed.astimezone(UTC)


def verify_binding(
    document: Mapping[str, Any],
    commit: str,
    fingerprint: str,
    environment: Mapping[str, str],
    now: datetime,
) -> None:
    if type(document.get("version")) is not int or document["version"] != 1:
        raise QualificationSafetyError("evidence_version_unknown")
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None or document.get("commit") != commit:
        raise QualificationSafetyError("evidence_commit_stale")
    if document.get("source_fingerprint") != fingerprint:
        raise QualificationSafetyError("evidence_source_changed")
    if document.get("environment") != dict(environment):
        raise QualificationSafetyError("evidence_environment_changed")
    age = (now - utc(document.get("captured_at"))).total_seconds()
    if not 0 <= age <= 86400:
        raise QualificationSafetyError("evidence_date_stale")
    if document.get("dataset") not in ("authentic", "synthetic", "mixed"):
        raise QualificationSafetyError("evidence_dataset_unknown")


def qualify(
    root: Path,
    evidence_root: Path,
    commit: str,
    phase: str,
    *,
    now: datetime | None = None,
    environment: Mapping[str, str] = ENVIRONMENT_IDENTITY,
    external_root: Path | None = None,
    external_corpus: Path | None = None,
    external_bronze: Path | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    if phase not in ("R0", "all"):
        raise QualificationSafetyError("qualification_phase_unavailable")
    if (external_root is None) != (external_corpus is None):
        raise QualificationSafetyError("external_paths_required_together")
    if external_bronze is not None and external_corpus is None:
        raise QualificationSafetyError("external_paths_required_together")
    if external_corpus is not None and phase != "R0":
        raise QualificationSafetyError("external_packet_only_for_R0")
    fingerprint = source_fingerprint(root)
    reason: str | None = None
    bundle: dict[str, Any] = {}
    try:
        bundle = load_json_report(evidence_root / "bundle.json")
        verify_binding(bundle, commit, fingerprint, environment, now)
        if not isinstance(bundle.get("evidence"), dict) or set(bundle["evidence"]) - KNOWN_EVIDENCE:
            raise QualificationSafetyError("evidence_catalog_invalid")
    except (OSError, QualificationSafetyError) as error:
        reason = str(error) if isinstance(error, QualificationSafetyError) else "evidence_missing"
    evidence = bundle.get("evidence", {}) if reason is None else {}
    registry = {item.source_id: item for item in load_sources(root / "registry/sources.yaml")}
    cache: dict[str, dict[str, Any]] = {}

    def path(key: str) -> Path:
        reference = evidence.get(key)
        if not isinstance(reference, dict):
            raise QualificationSafetyError("evidence_missing")
        return evidence_path(evidence_root, reference)

    def report(key: str) -> dict[str, Any]:
        if key not in cache:
            document = load_json_report(path(key))
            producer_environment = environment
            if external_corpus is not None and external_bronze is not None and key in (
                "corpus", "provenance", "rebuild"
            ):
                producer_environment = {
                    "producer": PRODUCER,
                    "backend_image_id": environment.get("backend_image_id", ""),
                }
                if re.fullmatch(
                    r"sha256:[0-9a-f]{64}", producer_environment["backend_image_id"]
                ) is None:
                    raise QualificationSafetyError("external_backend_identity_missing")
            verify_binding(document, commit, fingerprint, producer_environment, now)
            cache[key] = document
        return cache[key]

    external_measure: dict[str, Any] | None = None

    def compute(identity: str) -> dict[str, Any]:
        nonlocal external_measure
        if identity == "e2e" and "e2e_receipt" in evidence:
            receipt = report("e2e_receipt")
            counts = e2e_counts(receipt, evidence_root)
            return metrics.measurement(counts["checks"], counts["checks"], True, counts=counts)
        if identity in ("backend", "e2e"):
            inventory = report(identity + "_inventory")
            cases = inventory.get("cases")
            if not isinstance(cases, list):
                raise QualificationSafetyError("junit_inventory_missing")
            counts = junit_counts(path(identity + "_junit"), inventory=cases)
            if identity == "backend" and counts["integration_tests"] == 0:
                raise QualificationSafetyError("backend_integrations_missing")
            return metrics.measurement(counts["tests"], counts["tests"], True, counts=counts)
        if identity == "frontend":
            receipt = report("frontend_receipt")
            counts = frontend_counts(receipt, load_json_report(path("frontend_vitest")))
            return metrics.measurement(counts["tests"], counts["tests"], True, counts=counts)
        if identity == "corpus":
            receipt = report("corpus")
            if external_root is not None and external_corpus is not None:
                measured = inspect_packet(root, external_root, external_corpus)
                if receipt.get("packet_sha256") != measured["packet_sha256"]:
                    raise QualificationSafetyError("external_packet_receipt_mismatch")
            else:
                measured = validate_manifest(root / "backend", load_manifest(root / "backend"))
            documents = len(measured["authentic_documents"])
            cells = measured["verified_annotation_cells"]
            return metrics.measurement(
                documents,
                measured["files"],
                documents > 0 and cells > 0,
                annotation_cells=cells,
                scope=measured["scope"],
                **({"packet_sha256": measured["packet_sha256"]} if external_corpus else {}),
            )
        if external_corpus is not None and identity in ("provenance", "llm_gold", "rebuild"):
            if external_root is None or external_bronze is None:
                raise QualificationSafetyError("external_producer_binding_pending")
            if not evidence.get("corpus") == evidence.get("provenance") == evidence.get("rebuild"):
                raise QualificationSafetyError("external_replay_receipts_not_shared")
            if external_measure is None:
                packet = inspect_packet(root, external_root, external_corpus)
                native = report("rebuild")
                external_measure = verify_external_replay(
                    native, external_corpus, external_bronze, packet["packet_sha256"], evidence_root
                )
            value = external_measure
            if identity == "rebuild":
                return metrics.measurement(0, value["observations"], True, **value)
            if identity == "llm_gold":
                return metrics.measurement(0, value["observations"], True)
            return metrics.measurement(value["valid"], value["observations"], True, **value)
        if identity in ("provenance", "llm_gold"):
            document = report("provenance")
            if document["dataset"] == "authentic":
                corpus_manifest = load_manifest(root / "backend")
                validate_manifest(root / "backend", corpus_manifest)
                authentic_shas = {
                    entry["sha256"]
                    for entry in corpus_manifest["entries"]
                    if entry["authenticity"] == "authentic"
                    and entry["origin"]["kind"] == "official_acquisition"
                }
                if any(
                    item.get("content_sha256") not in authentic_shas
                    for item in metrics.rows(document, "references")
                ):
                    raise QualificationSafetyError("evidence_reference_not_authentic")
            value = metrics.provenance(document, evidence_root)
            if identity == "llm_gold":
                return metrics.measurement(
                    value["llm_unverified"],
                    value["denominator"],
                    value["passed"] and value["llm_unverified"] == 0,
                )
            return value
        if identity == "sources":
            return metrics.source_counts(report("sources"), registry, evidence_root, now)
        functions = {
            "parsing": metrics.parsing,
            "golden": metrics.golden,
            "rebuild": metrics.rebuild,
            "forecasts": metrics.forecasts,
            "api": metrics.api_latency,
            "copilot": metrics.copilot,
            "bulletin": metrics.bulletin,
        }
        return functions[identity](report(CRITERIA[identity][1]))

    results = []
    for identity, (threshold, evidence_key) in CRITERIA.items():
        entry: dict[str, Any] = {
            "id": identity,
            "state": "unknown",
            "measure": None,
            "threshold": threshold,
            "dataset": None,
            "proof": evidence.get(evidence_key),
            "reason": reason,
            "numerator": None,
            "denominator": None,
        }
        if reason is None:
            try:
                value = compute(identity)
                dataset = report(
                    "e2e_receipt"
                    if identity == "e2e" and "e2e_receipt" in evidence
                    else identity + "_inventory"
                    if identity in ("backend", "e2e")
                    else evidence_key
                )["dataset"]
                entry.update(
                    state="passed" if value["passed"] else "failed",
                    measure=value,
                    numerator=value["numerator"],
                    denominator=value["denominator"],
                    dataset=dataset,
                    reason="threshold_met" if value["passed"] else "threshold_not_met",
                )
                if identity not in ("backend", "frontend", "e2e") and dataset != "authentic":
                    entry.update(state="failed", reason="demonstration_only")
            except (
                OSError,
                KeyError,
                TypeError,
                ValueError,
                ArithmeticError,
                AttributeError,
            ) as error:
                entry["reason"] = (
                    str(error)
                    if isinstance(error, QualificationSafetyError)
                    else "evidence_invalid"
                )
        results.append(entry)
    required = R0_REQUIRED if phase == "R0" else set(CRITERIA)
    passed = bundle.get("dataset") == "authentic" and all(
        item["state"] == "passed" for item in results if item["id"] in required
    )
    return {
        "version": 1,
        "phase": phase,
        "commit": commit,
        "source_fingerprint": fingerprint,
        "environment": dict(environment),
        "captured_at": now.isoformat(),
        "dataset": bundle.get("dataset"),
        "criteria": results,
        "required": sorted(required),
        "passed": passed,
        "exit_code": 0 if passed else 1,
        "scope": (
            "démonstration logicielle"
            if bundle.get("dataset") in ("synthetic", "mixed")
            else ("fiabilité logicielle R0" if phase == "R0" else "KPI MVP sur preuves importées")
        ),
        "operational_passed": phase == "all" and passed,
        "program_R6_complete": False,
        "deployment_observed": False,
        "human_acceptance_observed": False,
    }


def markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Qualification mesurée",
        "",
        f"Statut : {'PASSED' if report['passed'] else 'PARTIAL'} — {report['scope']}",
        f"Commit : {report['commit']}",
        "",
        "| Critère | État | Numérateur / dénominateur | Dataset | Raison |",
        "|---|---|---|---|---|",
    ]
    for item in report["criteria"]:
        lines.append(
            f"| {item['id']} | {item['state']} | {item['numerator']} / {item['denominator']} "
            f"| {item['dataset'] or 'unknown'} | {item['reason']} |"
        )
    lines.extend(
        ["", "Ni R6.11, ni déploiement, ni essai humain ne sont déduits de ce rapport.", ""]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("R0", "all"))
    parser.add_argument("--root", type=Path, default=Path("/workspace"))
    parser.add_argument("--evidence", default="docs/evidence/qualification")
    parser.add_argument("--commit", required=True)
    parser.add_argument("--external-root", type=Path)
    parser.add_argument("--external-corpus", type=Path)
    parser.add_argument("--external-bronze", type=Path)
    parser.add_argument("--external-evidence", type=Path)
    parser.add_argument("--reports", type=Path, default=Path("/reports/qualification"))
    args = parser.parse_args()
    try:
        relative = Path(args.evidence)
        target = (args.root / relative).resolve()
        if (
            relative.is_absolute()
            or "\\" in args.evidence
            or ".." in relative.parts
            or not target.is_relative_to(args.root.resolve())
        ):
            raise QualificationSafetyError("evidence_outside_repository")
        if args.external_evidence is not None:
            if args.external_corpus is None or not args.external_evidence.is_absolute():
                raise QualificationSafetyError("external_evidence_requires_packet")
            target = args.external_evidence.resolve(strict=True)
            if target.is_relative_to(args.root.resolve()) or not target.is_dir():
                raise QualificationSafetyError("external_evidence_must_be_outside_repository")
        result = qualify(
            args.root,
            target,
            args.commit,
            args.phase,
            environment=native_environment(),
            external_root=args.external_root,
            external_corpus=args.external_corpus,
            external_bronze=args.external_bronze,
        )
        directory = args.reports / uuid4().hex
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "qualification.json").write_text(json.dumps(result, indent=2) + "\n")
        (directory / "qualification.md").write_text(markdown(result))
        sys.stdout.write(
            json.dumps(
                {
                    "passed": result["passed"],
                    "phase": args.phase,
                    "report": str(directory),
                    "exit_code": result["exit_code"],
                }
            )
            + "\n"
        )
        return int(result["exit_code"])
    except (OSError, ValueError) as error:
        reason = (
            str(error) if isinstance(error, QualificationSafetyError) else "qualification_invalid"
        )
        sys.stderr.write(reason + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
