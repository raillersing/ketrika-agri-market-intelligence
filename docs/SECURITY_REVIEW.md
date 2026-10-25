# Revue de sécurité courante — réserves ouvertes

État2026-10-25, source b7e63ee. L'ancienne conclusion « conforme » est conservée dans [l'historique](audits/2026-10-25/history/SECURITY_REVIEW.md), sans valeur de réception actuelle. [Audit indépendant](audits/2026-10-25/INDEPENDENT_AUDIT.md), [lots AU-04–07/AU-24–25](audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

| Contrôle | Preuve actuelle | État |
|---|---|---|
| Accès métier | Plusieurs lectures sans session ; cookie arbitraire accepte l'accueil ; admin/review et collecte restent protégés | Défaut à corriger IA-06 |
| Logout | Révocation refusée dans le processus émetteur, acceptée dans un autre processus isolé du même module | Non durable IA-08 |
| HTTPS/configuration prod | Cookie Secure=false ; defaults et seed admin démo non refusés en prod | Non reçu IA-08 |
| Notifications | Les deux chemins SMTP atteignent un transport intercepté avec gate off ; aucun envoi réel durant l'audit | H3 incomplet IA-07 |
| Dépendances web |61 avis dont8 critiques selon scan complet ;42 avis dont5 critiques en production selon scan séparé | Triage et corrections requis IA-09 |
| Dépendances Python |44 identifiants d'avis sur cinq packages du lock runtime+geo+ml, doublons par alias possibles | Corrections requises IA-09 |
| Restauration | Code pg_restore=1 accepté ; contrôle d'intégrité non fermé quand manifeste/outil absents | Non reçu IA-17 |
| Secrets | Scans incrémentaux historiques disponibles ; scan du présent delta à réception documentaire | Ne pas déduire un nouvel audit global de l'historique |

Détails et sorties brutes : [evidence](audits/2026-10-25/evidence). Une version affectée n'est pas une exploitation prouvée. Distinguer dépendances dev/runtime, Linux/Windows, fonctionnalités activées et mesures réellement testées.

L'avis [Next.js GHSA-f82v-jwr5-mffw](https://github.com/vercel/next.js/security/advisories/GHSA-f82v-jwr5-mffw) concerne le middleware ; l'ancienne justification « pas de Server Actions » ne traite pas cet avis. Next14.2.10 est dans la plage indiquée par le mainteneur. Ne pas conclure qu'un seul patch historique traite tous les avis actuels.

L'avis [Vitest GHSA-5xrq-8626-4rwp](https://github.com/vitest-dev/vitest/security/advisories/GHSA-5xrq-8626-4rwp) est conditionnel au serveur UI/Browser Mode ; aucun serveur Vitest exposé n'a été démontré ici. Les correctifs et éventuelles majeures doivent être décidés par ADR/SPECS puis reçus sur la stack retenue.

Aucun pentest destructif, restauration active, accès tiers ni envoi réel. Cet audit n'autorise pas à acheter/provisionner ni à lever H3/H7.

## Correction reçue H3 —25 octobre2026

AU-05 / ADR122, contenu5400f39 : trois transports SMTP limités à Mailpit dev/test exact1025 ; aucune construction externe/prod ni Telegram, même flag1.32 tests négatifs/positifs ciblés, trois véritables captures internes et check complet2426/52+12 E2E verts. Logs sans destinataire/token/erreur transport brute. Aucun envoi réel autorisé.

Un faux positif generic-api-key détecte le tag de déduplication SYNTHETIC_AU05 dans le seul diagnostic. .gitleaksignore cible uniquement commit5400f39/chemin/règle/ligne33 ; reprise deux commits153668octets/zéro secret. Les risques authentification/révocation/configuration et dépendances demeurent ouverts ; code AU-04 en développement isolé, pas de nouvelle qualification de déploiement.
