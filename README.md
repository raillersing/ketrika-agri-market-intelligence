# Ketrika Agri Market Intelligence

Plateforme de veille de marché et d'intelligence économique sur les **produits PPN vivriers à Madagascar** (riz, maïs, manioc, huile, sucre, légumineuses, farine) avec traçabilité et **provenance vérifiable à 100 %**.

---

## Documentation normative

- [AGENTS.md](AGENTS.md) : Constitution normative de l'agent autonome.
- [docs/plan/SPECS.md](docs/plan/SPECS.md) : Spécifications techniques et contrats d'architecture.
- [docs/plan/MVP_EXECUTION_PLAN.md](docs/plan/MVP_EXECUTION_PLAN.md) : Plan d'exécution par tâches et critères d'acceptation.
- [docs/plan/PROGRESS.md](docs/plan/PROGRESS.md) : Registre d'avancement et journal de bord.
- [docs/plan/DECISIONS.md](docs/plan/DECISIONS.md) : Registre des décisions d'architecture (ADR).
- [docs/plan/BLOCKERS.md](docs/plan/BLOCKERS.md) : Registre des incidents et replis.

---

## Démarrage rapide (Local Dev)

Prérequis : Windows PowerShell, Docker Desktop avec Docker Compose v2+.

```powershell
# Vérification des prérequis et lancement
./scripts/dev.ps1 up

# Vérification qualité et tests
./scripts/dev.ps1 check
./scripts/dev.ps1 test
```
