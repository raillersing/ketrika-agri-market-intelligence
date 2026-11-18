"""DataOps diagnostic and source health classification (SPECS §19, IA-DATA-02).

Classifies source ingestion runs into 8 operational states:
- downloaded: Bronze artifact collected and stored under SHA-256
- parsed: Raw document parsed into structured record batches
- normalized: Records validated and loaded into Silver observations
- published: Verified, passed provenance gates, and materialized in Gold views
- no_data: Run finished normally but produced 0 new observations / 0 documents
- policy_blocked: Stopped by policy engine (robots.txt, 401/403, rate budget, SSRF)
- schema_drift: Schema contract mismatch or drift detected in source structure
- failed: Upstream connection error, timeout, server 5xx, or crash
- idle: Source registered, waiting for first execution

Never exposes secrets, API tokens, internal passwords, database connection
strings, or private filesystem paths in diagnostic codes and messages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

DataOpsDiagnosticStatus = Literal[
    "downloaded",
    "parsed",
    "normalized",
    "published",
    "no_data",
    "policy_blocked",
    "schema_drift",
    "failed",
    "idle",
]


@dataclass(frozen=True)
class DiagnosticOutcome:
    """Sanitized DataOps diagnostic outcome for public exposition."""

    diagnostic_status: DataOpsDiagnosticStatus
    diagnostic_code: str
    diagnostic_message: str
    error_category: str | None = None


# Patterns for classifying errors into safe, stable diagnostic codes
_ROBOTS_PATTERN = re.compile(r"robots(\.txt)?", re.IGNORECASE)
_RATE_BUDGET_PATTERN = re.compile(r"(rate|budget|too_many_requests|429)", re.IGNORECASE)
_AUTH_PATTERN = re.compile(r"(401|403|unauthorized|forbidden|credentials|auth)", re.IGNORECASE)
_POLICY_PATTERN = re.compile(r"(policy_stop|policystop|policy|disabled)", re.IGNORECASE)
_SCHEMA_PATTERN = re.compile(
    r"(schema|schema_drift|contract|shape|column|variant|type_mismatch)", re.IGNORECASE
)
_CONNECT_PATTERN = re.compile(
    r"(connecterror|connection.*refused|dns|gaierror|name_not_resolved|unreachable)", re.IGNORECASE
)
_TIMEOUT_PATTERN = re.compile(r"(timeout|timed_out|readtimeout|connecttimeout)", re.IGNORECASE)
_SERVER_ERROR_PATTERN = re.compile(r"(500|502|503|504|internal_server_error)", re.IGNORECASE)
_NOT_FOUND_PATTERN = re.compile(r"(404|not_found)", re.IGNORECASE)


def sanitize_diagnostic_error(
    raw_error: str | None,
) -> tuple[DataOpsDiagnosticStatus, str, str, str]:
    """Map raw exception text to a sanitized status, stable code, user message, and category.

    Guarantees that no secret, path, token or raw traceback is exposed.
    """
    if not raw_error:
        return (
            "failed",
            "COLLECTION_FAILED",
            "Échec de collecte ou traitement interrompu.",
            "unknown",
        )

    err = str(raw_error).strip()

    # 1. Policy blocked
    if _ROBOTS_PATTERN.search(err):
        return (
            "policy_blocked",
            "POLICY_STOP_ROBOTS",
            "Collecte suspendue conformément aux directives du fichier robots.txt de la source.",
            "policy",
        )
    if _RATE_BUDGET_PATTERN.search(err):
        return (
            "policy_blocked",
            "POLICY_STOP_RATE_LIMIT",
            "Quota journalier ou limite de fréquence atteinte pour cette source.",
            "policy",
        )
    if _AUTH_PATTERN.search(err):
        return (
            "policy_blocked",
            "POLICY_STOP_AUTH_REQUIRED",
            "Accès restreint ou authentification requise par l'organisme fournisseur.",
            "policy",
        )
    if _POLICY_PATTERN.search(err):
        return (
            "policy_blocked",
            "POLICY_STOP_BLOCKED",
            "Collecte interrompue par les garde-fous de politique éthique ou source désactivée.",
            "policy",
        )

    # 2. Schema drift
    if _SCHEMA_PATTERN.search(err):
        if "contract_absent" in err.lower():
            return (
                "schema_drift",
                "SCHEMA_CONTRACT_ABSENT",
                "Aucun contrat de schéma déclaré pour ce format de document source.",
                "schema",
            )
        return (
            "schema_drift",
            "SCHEMA_DRIFT_MISMATCH",
            "Changement de structure détecté dans les données de la source (colonnes ou formats inattendus).",
            "schema",
        )

    # 3. Upstream network / HTTP errors
    if _CONNECT_PATTERN.search(err):
        return (
            "failed",
            "UPSTREAM_CONNECT_ERROR",
            "Impossible de joindre le serveur source (serveur injoignable ou incident réseau).",
            "network",
        )
    if _TIMEOUT_PATTERN.search(err):
        return (
            "failed",
            "UPSTREAM_TIMEOUT",
            "Délai d'attente dépassé lors de la communication avec la source.",
            "network",
        )
    if _SERVER_ERROR_PATTERN.search(err):
        return (
            "failed",
            "UPSTREAM_HTTP_500",
            "Le serveur source distant est temporairement en panne ou indisponible (erreur HTTP 5xx).",
            "upstream",
        )
    if _NOT_FOUND_PATTERN.search(err):
        return (
            "failed",
            "UPSTREAM_HTTP_404",
            "Le document ou l'endpoint d'API source est introuvable (erreur HTTP 404).",
            "upstream",
        )

    # Fallback safe error
    return (
        "failed",
        "COLLECTION_FAILED",
        "Traitement interrompu ou anomalie d'acquisition détectée.",
        "unknown",
    )


def classify_run_diagnostic(
    status: str | None,
    n_records: int | None = None,
    n_fetched: int | None = None,
    error: str | None = None,
    has_published_gold: bool = False,
    open_review_items: int = 0,
) -> DiagnosticOutcome:
    """Classify run state into one of 8 canonical DataOps diagnostic states."""
    if status is None:
        return DiagnosticOutcome(
            diagnostic_status="idle",
            diagnostic_code="IDLE_NOT_RUN",
            diagnostic_message="Source enregistrée, en attente de première collecte.",
            error_category=None,
        )

    norm_status = status.strip().lower()

    if norm_status == "running":
        return DiagnosticOutcome(
            diagnostic_status="downloaded",
            diagnostic_code="IN_PROGRESS",
            diagnostic_message="Collecte et traitement des données en cours.",
            error_category=None,
        )

    if norm_status == "success":
        records_count = n_records or 0
        fetched_count = n_fetched or 0
        if records_count == 0 and fetched_count == 0:
            return DiagnosticOutcome(
                diagnostic_status="no_data",
                diagnostic_code="NO_NEW_DATA",
                diagnostic_message="Collecte terminée avec succès : aucune nouvelle observation disponible chez l'éditeur.",
                error_category=None,
            )
        if records_count == 0:
            return DiagnosticOutcome(
                diagnostic_status="no_data",
                diagnostic_code="NO_OBSERVATIONS_PARSED",
                diagnostic_message="Documents collectés avec succès, mais aucune observation exploitable n'a été extraite.",
                error_category=None,
            )
        if has_published_gold:
            return DiagnosticOutcome(
                diagnostic_status="published",
                diagnostic_code="PUBLISHED_GOLD",
                diagnostic_message=f"Données vérifiées et publiées avec succès dans les indicateurs Gold ({records_count} obs).",
                error_category=None,
            )
        if open_review_items > 0:
            return DiagnosticOutcome(
                diagnostic_status="normalized",
                diagnostic_code="REVIEW_REQUIRED",
                diagnostic_message=f"Données normalisées en Silver ({records_count} obs) ; {open_review_items} élément(s) en attente de revue humaine.",
                error_category="review",
            )
        return DiagnosticOutcome(
            diagnostic_status="normalized",
            diagnostic_code="NORMALIZED_SILVER",
            diagnostic_message=f"Données collectées et normalisées en Silver avec succès ({records_count} obs).",
            error_category=None,
        )

    if norm_status == "failed":
        diag_status, diag_code, diag_msg, err_cat = sanitize_diagnostic_error(error)
        return DiagnosticOutcome(
            diagnostic_status=diag_status,
            diagnostic_code=diag_code,
            diagnostic_message=diag_msg,
            error_category=err_cat,
        )

    # Any other status (e.g. 'interrupted', 'blocked', 'aborted')
    if norm_status == "blocked":
        return DiagnosticOutcome(
            diagnostic_status="policy_blocked",
            diagnostic_code="POLICY_STOP_BLOCKED",
            diagnostic_message="Source bloquée par les politiques éthiques ou désactivée.",
            error_category="policy",
        )

    diag_status, diag_code, diag_msg, err_cat = sanitize_diagnostic_error(error or norm_status)
    return DiagnosticOutcome(
        diagnostic_status=diag_status,
        diagnostic_code=diag_code,
        diagnostic_message=diag_msg,
        error_category=err_cat,
    )
