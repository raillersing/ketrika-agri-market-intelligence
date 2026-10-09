# BACKLOG : idées hors périmètre et dettes techniques

> Règle (AGENTS.md §7) : Aucun `TODO` ni `FIXME` dans le code sans entrée correspondante ici.

| ID | Date | Tâche source | Description | Catégorie | Priorité post-MVP |
|---|---|---|---|---|---|
| BL-001 | 2026-10-05 | Cadrage | Connecteurs marketplaces privées (Tantsah, CoinAfrique) sous réserve d'accord/API | Feature | High |
| BL-002 | 2026-10-05 | Cadrage | OCR de PDF scannés pour archives historiques dégradées | Extraction | Medium |
| BL-003 | 2026-10-05 | Cadrage | Intégration raster satellite Sentinel-2 / Landsat haute résolution (30m) | Geo / ML | Low |
| BL-004 | 2026-10-05 | Cadrage | Alertes et diffusion via canal WhatsApp / SMS | Diffusion | High |
| BL-005 | 2026-10-05 | Cadrage | Modélisation des prévisions au niveau commune | ML | Medium |
| BL-006 | 2026-10-07 | T11.2 | Migration majeure Next.js 15+ / React 19 pour alignement sur les derniers patchs d'amont | Security / Web | Medium |
| BL-007 | 2026-10-07 | T11.2 | Migration majeure MapLibre GL JS vers 6.5+ après validation de compatibilité des couches vectorielles | Security / Geo | Low |
| BL-008 | 2026-10-09 | R0.3 | Mesurer et optimiser la première copie Docker des volumes QA : /app contient aussi .venv alors qu'un volume dédié est monté sur /app/.venv. Évaluer une séparation source/dépendances ou nocopy avec init de permissions strictement bornée aux volumes QA ; garder non-root et preuves fail-closed. Aucun nettoyage de Bronze, de volumes historiques ou de caches partagés autorisé | Performance / QA | Medium |
| BL-009 | 2026-10-09 | R0.3 / R2.10 | UI tierce 65541c8/799f869 : captures QA à zéro puis 16 observations synthétiques affichent badges statiques 100 % provenance, 3 alertes et stack 6/6 ; graphique vide malgré tableau. Ce ne sont pas des mesures qualifiées ; préserver le design mais afficher états/dénominateurs source-backed, contexte QA/non qualifié et graphique vérifié dans R2.10, avec tests valeurs/API/reload. Aucun E2E d'auth ne qualifie ces chiffres | Data truthfulness / Web | High |
