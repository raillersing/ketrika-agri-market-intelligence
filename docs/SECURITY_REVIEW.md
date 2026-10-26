# Revue de sécurité courante — réserves ouvertes

État actualisé2026-10-26. L'audit initial portait sur b7e63ee ; ses défauts ne décrivent pas automatiquement les corrections reçues. L'ancienne conclusion « conforme » est conservée dans [l'historique](audits/2026-10-25/history/SECURITY_REVIEW.md), sans valeur de réception actuelle. [Audit indépendant](audits/2026-10-25/INDEPENDENT_AUDIT.md), [lots AU-04–07/AU-24–25](audits/2026-10-25/CORRECTIVE_EXECUTION_PLAN.md).

| Contrôle | Preuve actuelle | État |
|---|---|---|
| Accès métier | Matrice serveur, vrai login, cookie arbitraire et révoqué refusés ;57 tests web et15 E2E sur2a6ec4e | AU-04 reçu logiciel, activation séparée |
| Logout | Révocation SQL partagée entre clients et processus ; digest seul, panne SQL fermée | AU-04 reçu logiciel |
| HTTPS/configuration prod | Secrets vides/démo et bootstrap démo refusés en prod ; cookie selon environnement explicite | Contrôles négatifs reçus, déploiement non évalué |
| Notifications | Trois transports limités à Mailpit dev/test ; externe et Telegram refusés même flag1 | AU-05 reçu logiciel, H3 reste fermé |
| Dépendances web | Lock corrigé Next15.5.28/React19.3.1 et transitoires ; audit npm complet zéro avis connus | AU-06 réception globale en cours |
| Dépendances Python | Cinq transitoires corrigés ; pip-audit2.10.1 sur export tous extras, code0/zéro avis connus | AU-06 réception globale en cours, Linux Python3.12 |
| Restauration | Erreurs propagées, clone neuf/manifestes obligatoires ; défaut de perte d'ACL trouvé puis corrigé,37 ciblés et vrais clones reçus | AU-07 réception globale requise sur7b29333 |
| Secrets | Scans incrémentaux historiques disponibles ; scan du présent delta à réception documentaire | Ne pas déduire un nouvel audit global de l'historique |

Détails et sorties brutes : [evidence](audits/2026-10-25/evidence). Une version affectée n'est pas une exploitation prouvée. Distinguer dépendances dev/runtime, Linux/Windows, fonctionnalités activées et mesures réellement testées.

L'avis [Next.js GHSA-f82v-jwr5-mffw](https://github.com/vercel/next.js/security/advisories/GHSA-f82v-jwr5-mffw) concerne le middleware ; l'ancienne justification « pas de Server Actions » ne traite pas cet avis. Next14.2.10 est dans la plage indiquée par le mainteneur. Ne pas conclure qu'un seul patch historique traite tous les avis actuels.

L'avis [Vitest GHSA-5xrq-8626-4rwp](https://github.com/vitest-dev/vitest/security/advisories/GHSA-5xrq-8626-4rwp) est conditionnel au serveur UI/Browser Mode ; aucun serveur Vitest exposé n'a été démontré ici. Les correctifs et éventuelles majeures doivent être décidés par ADR/SPECS puis reçus sur la stack retenue.

Aucun pentest destructif, restauration active, accès tiers ni envoi réel. Cet audit n'autorise pas à acheter/provisionner ni à lever H3/H7.

## Correction reçue H3 —25 octobre2026

AU-05 / ADR122, contenu5400f39 : trois transports SMTP limités à Mailpit dev/test exact1025 ; aucune construction externe/prod ni Telegram, même flag1.32 tests négatifs/positifs ciblés, trois véritables captures internes et check complet2426/52+12 E2E verts. Logs sans destinataire/token/erreur transport brute. Aucun envoi réel autorisé.

Un faux positif generic-api-key détecte le tag de déduplication SYNTHETIC_AU05 dans le seul diagnostic. Les exceptions historiques restent limitées aux introductions exactes de ce marqueur, sans ignore global. La réception AU-04 du26 octobre remplace l'ancien état de développement : [preuves](evidence/auth-20261026/RECEPTION.md). Aucun de ces tests ne qualifie un déploiement actif.

## Dépendances et restauration —26 octobre2026

[Audits et registres exacts](evidence/dependencies-restore-20261026/) : locks régénérés dans Docker, aucune suppression d'avis ou d'outil. Audit Python tous extras avec outil figé et hashes lock/export ; les marqueurs sont évalués sous Linux Python3.12. Ces résultats ne couvrent pas un environnement Windows natif Python, tous les paquets système des images ou des vulnérabilités non publiées. ESLint8 et cinq transitoires restent dépréciés, sans avis détecté dans ce scan ; la migration du lint demeure une dette de maintenance, pas une preuve d'exploitation ou une certification générale.

[Fidélité SQL ADR126](evidence/restore-acl-20261026/DEVELOPMENT.md) :78 tables/17542 lignes de fixture, propriétaires/ACL et droits effectifs identiques sur clones shell et PowerShell ; rôle absent provoque erreur1 et rollback réel. Les options supprimant les droits ont été retirées avant cette preuve. Aucun rôle ou objet Bronze actif touché, aucun restore de production qualifié. Les réceptions complètes des contenus applicatifs restent obligatoires avant clôture AU-06/AU-07.
