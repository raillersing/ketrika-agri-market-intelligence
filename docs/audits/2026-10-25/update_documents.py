"""Build the audit traceability matrix and refresh current documentation only."""

import json
import re
from pathlib import Path
from typing import Any

import yaml

from ketrika.core.execution_plan import read_states, read_tasks

ROOT = Path("/workspace")
AUDIT = ROOT / "docs/audits/2026-10-25"
plan_path = ROOT / "docs/plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md"
progress_path = ROOT / "docs/plan/PROGRESS.md"
original_plan = plan_path.read_text()
if "Audit20261025 :" in original_plan:
    raise SystemExit(
        "One-shot documentation migration already applied; review a new delta instead."
    )
states = read_states(progress_path.read_text())
tasks = read_tasks(original_plan)
assert len(tasks) == len(states) == 74


def disposition(task_id: str) -> tuple[str, str]:
    phase, index = map(int, task_id[1:].split("."))
    if phase == 0:
        return (
            ("Réception historique conservée, non recertifiée", "AU-01 à AU-09 si impact")
            if index <= 7
            else (
                ("Partiel : défauts bloquants / corpus incomplet", "AU-01 à AU-09")
                if index == 8
                else ("Gate non reçu", "AU-09")
            )
        )
    if phase == 1:
        if index in (1, 2, 10):
            return "Code/référentiels présents, qualification actuelle à compléter", "AU-10"
        if index == 13:
            return "Gate non reçu", "AU-11"
        if index == 8:
            return "WB partiellement live vérifiée, estimations imputées seulement", "AU-11"
        if index in (3, 7, 11):
            return "Code présent ; politique de source arrêtée à respecter", "AU-11"
        return "Code présent ; réception opérationnelle non prouvée ici", "AU-11"
    if phase == 2:
        if index == 11:
            return "Gate non reçu", "AU-13"
        if index == 10:
            return "UI partielle : faux accueil, carte et filtres à corriger", "AU-01 / AU-13"
        if index in (5, 6, 7):
            return "Connecteur présent ; aucune ligne macro dans la base sondée", "AU-12"
        if index == 8:
            return "Code présent ; publication retenue avec503, non qualifiée", "AU-12"
        return "Contrats/helpers présents ; réception données et parcours incomplète", "AU-12"
    if phase == 3:
        if index == 2:
            return "Chemin SQL as-of en échec, helper non raccordé au pipeline", "AU-14"
        if index == 1:
            return "Éligibilité présente, cohorte réelle à recevoir", "AU-14"
        if index == 9:
            return "Gate non reçu", "AU-16"
        if index in (7, 8):
            return "Publication héritée non qualifiée / évaluation réelle absente", "AU-16"
        return "Algorithmes présents ; raccordement protocole à recevoir", "AU-15"
    if phase == 4:
        if index in (9, 10):
            return "Connecteur absent, statut unavailable explicite", "AU-19"
        if index == 8:
            return "Calcul NDVI/VCI présent ; acquisition/persistance absentes du parcours", "AU-19"
        if index == 12:
            return "Gate non reçu", "AU-18"
        if index == 11:
            return "API/UI présentes mais réponses de repli fabriquées", "AU-02 / AU-18"
        if index in (6, 7):
            return "Calcul/référentiel présent ; preuves réelles insuffisantes", "AU-18"
        return "Connecteur/contrat présent ; données réelles et versions à recevoir", "AU-17"
    if phase == 5:
        if index in (8, 9):
            return "Parcours préparés / gate non reçu, entrées fixes à retirer", "AU-03 / AU-22"
        if index in (4, 5, 7):
            return (
                "Calcul présent ; références/validation et raccordements incomplets",
                "AU-03 / AU-21",
            )
        return "Contrat/parseur/bilan présent ; corpus quantitatif recevable à acquérir", "AU-20"
    if index in (1, 2, 3, 4):
        return "Parcours/helpers présents ; intégration opérationnelle non reçue", "AU-22"
    if index in (5, 6):
        return "Code présent ; contenus réels et notification sûre à recevoir", "AU-05 / AU-23"
    if index == 7:
        return "Défauts sécurité confirmés, gate non reçu", "AU-04 / AU-06 / AU-25"
    if index == 8:
        return "Helpers/scripts présents mais garde/erreurs insuffisants", "AU-07 / AU-24"
    if index == 9:
        return "Supervision en mémoire, raccordement durable manquant", "AU-24"
    if index == 10:
        return "Paquet préparé ; performance et durcissement non reçus ici", "AU-25"
    return "Réception finale non atteinte", "AU-26"


headings = {
    m.group(1): m.group(2) for m in re.finditer(r"(?m)^### (R\d+\.\d+) — (.+)$", original_plan)
}
rows: list[dict[str, Any]] = []
for task_id, task in tasks.items():
    state, lots = disposition(task_id)
    rows.append(
        {
            "task_id": task_id,
            "title": headings[task_id],
            "priority": task.priority,
            "historical_status": states[task_id].status,
            "dependencies": sorted(task.dependencies),
            "conditional_dependencies": task.condition,
            "audit_disposition": state,
            "corrective_lots": lots,
        }
    )
AUDIT.joinpath("task_matrix.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
matrix = [
    "# Matrice indépendante des74 tâches et capacités",
    "",
    "Date2026-10-25, source b7e63ee. Statut historique ≠ présence du code ≠ qualification réelle.",
    "Les statuts de PROGRESS et du miroir sont conservés ; ce document ne reçoit aucun gate.",
    "Dépendances exactes/conditionnelles : task_matrix.json et plan R normatif. Les chemins et réceptions par lot figurent dans CORRECTIVE_EXECUTION_PLAN.md.",
    "",
    "| Tâche | Priorité / statut canonique | Objectif | Constat indépendant | Suite |",
    "|---|---|---|---|---|",
]
for row in rows:
    matrix.append(
        f"| {row['task_id']} | {row['priority']} / {row['historical_status']} | {row['title']} | {row['audit_disposition']} | {row['corrective_lots']} |"
    )
matrix += [
    "",
    "## Sources : configuration distincte de qualification",
    "",
    "État SQL lu dans runtime.json ; aucune nouvelle collecte ni nouvelle vérification HTTP des URL sources. Une entrée active n'est pas une capacité live reçue.",
    "",
    "| Source | Registre | SQL | Module déclaré présent | Limite actuelle |",
    "|---|---|---|---|---|",
]
registry_rows = yaml.safe_load((ROOT / "registry/sources.yaml").read_text())
assert isinstance(registry_rows, list)
registry = {row["source_id"]: row for row in registry_rows}
runtime = json.loads(AUDIT.joinpath("evidence/runtime.json").read_text())
sql_status = {row["source_id"]: row["status"] for row in runtime["sql"]["source_status"]}
for source_id, source in registry.items():
    module = str(source.get("connector", "")).split(":")[0]
    module_present = (ROOT / "backend/src" / (module.replace(".", "/") + ".py")).exists()
    limit = (
        "WB :135 prix courants imputés ; périmètre partiel"
        if source_id == "wb_rtfp_mdg"
        else "Source arrêtée : aucune relance, archives autorisées seulement"
        if source.get("status") == "disabled"
        else "Pas de réception live actuelle déduite de la présence du code"
    )
    matrix.append(
        f"| {source_id} | {source.get('status')} | {sql_status.get(source_id, 'absent de la lecture SQL')} | {'oui' if module_present else 'non (référentiel/import à examiner)'} | {limit} |"
    )
    source_doc = ROOT / "docs/sources" / (source_id + ".md")
    if source_doc.exists():
        body = source_doc.read_text()
        first, rest = body.split("\n", 1)
        notice = f"\n> Audit indépendant2026-10-25 : registre `{source.get('status')}`, SQL `{sql_status.get(source_id, 'absent')}`. {limit}. Les dates/HTTP/droits/annotations ci-dessous sont des descriptions historiques, non revérifiées par cet audit. Réception à suivre dans [la matrice](../audits/2026-10-25/TASK_CAPABILITY_MATRIX.md) et le [plan correctif](../audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).\n"
        source_doc.write_text(first + "\n" + notice + rest)
matrix += [
    "",
    "## Lecture des absences",
    "",
    "FIRMS et GloFAS : pas de connecteur enregistré. Copernicus NDVI : fonctions de calcul présentes, acquisition et chaîne publiée non réalisées dans le parcours inspecté. Carte géographique : composant actuel en cartes textuelles, rendu GeoJSON non implémenté. Supervision : helpers en mémoire, persistance/raccordement manquants. Les autres modules ont du code ; les réécrire intégralement serait redondant.",
]
AUDIT.joinpath("TASK_CAPABILITY_MATRIX.md").write_text("\n".join(matrix) + "\n")


# Preserve old evidence columns and statuses; make their historical nature unambiguous.
def refresh_rows(document: str, canonical: bool) -> str:
    output = []
    for line in document.splitlines():
        if not line.startswith("| R"):
            output.append(line)
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if parts[0] not in tasks:
            output.append(line)
            continue
        task_id = parts[0]
        state, lots = disposition(task_id)
        old = parts[-1]
        if canonical:
            parts[-1] = f"Audit20261025 : {state} ; {lots}. Historique : {old}"
        else:
            parts[-1] = (
                f"Audit20261025 : {state} ; {lots}. Preuve historique (non réception actuelle) : {old}"
            )
        output.append("| " + " | ".join(parts) + " |")
    return "\n".join(output) + "\n"


plan_path.write_text(refresh_rows(original_plan, False))
progress_path.write_text(refresh_rows(progress_path.read_text(), True))


def historical_notice(path: str, label: str) -> None:
    target = ROOT / path
    body = target.read_text()
    first, rest = body.split("\n", 1)
    relative = "../audits" if target.parent.name in ("plan", "runbooks", "protocols") else "audits"
    target.write_text(
        first
        + f"\n\n> Mise à jour2026-10-25 : {label}. Voir [audit indépendant]({relative}/2026-10-25/INDEPENDENT_AUDIT.md) et [plan correctif]({relative}/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).\n"
        + rest
    )


historical_notice(
    "docs/MVP_REPORT.md",
    "rapport T historique conservé ; ses mentions100%/terminé ne certifient pas l'état courant R0–R6",
)
historical_notice(
    "docs/plan/MVP_EXECUTION_PLAN.md",
    "contrats et statuts T conservés ; aucune capacité actuelle requalifiée par leur historique",
)
for filename in (
    "restore.md",
    "deploy.md",
    "DEPLOYMENT_RUNBOOK.md",
    "OFFLINE_REBUILD_QUALIFICATION.md",
    "NATIVE_SILVER_RECOVERY.md",
    "manual-collection.md",
    "MEASURED_QUALIFICATION.md",
):
    label = "procédure à utiliser seulement dans son périmètre reçu ; programme PARTIAL"
    if filename in ("restore.md", "deploy.md", "DEPLOYMENT_RUNBOOK.md"):
        label = "restore.sh non qualifié pour une restauration fiable (IA-17), configuration prod non reçue ; corriger AU-04/06/07 avant usage ; aucune destination active autorisée"
    historical_notice("docs/runbooks/" + filename, label)
for filename in ("docs/DEMO_1.md", "docs/DEMO_2.md"):
    historical_notice(
        filename,
        "scénario de démonstration historique, aucune preuve de marché ou de qualification actuelle",
    )

print(json.dumps({"tasks": len(rows), "sources": len(registry), "statuses_preserved": True}))
