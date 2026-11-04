# Corpus des deux archives World Bank — R0.8 en cours

Les ZIP2026-09-28 et2026-10-05 sont conservés sans modification dans le volume
`ketrika_wb_source_archives_20261103_candidates`, monté en lecture seule.
Leurs URL, heures UTC de récupération, tailles, SHA et réponses200 sont dans
`docs/evidence/R0.8_CI_WB_ARCHIVES_20261103_ACQUISITION.json`.
L'heure de modification d'une fiche n'est pas une première publication connue.

Les60 valeurs de `R0.8_WB_ARCHIVE_20261104_ANNOTATIONS.json` ont été transcrites
par l'agent depuis les CSV originaux, avec une lecture standard ZIP/CSV distincte
du parser produit. Elles couvrent janvier2024 à juin2026, trente cellules par
édition au même grain. Aucune revue humaine revendiquée. Les unités KG et le
label Rice(local) viennent du contexte original, SHA4a9e254e…, pas du nom du
fichier ni d'une déduction globale sur rice_milled.

La série `gid_mdg_national_average` et ses trois libellés Market Average sont
publiés explicitement. Elle reste nationale. Les valeurs c_rice sont des
estimations imputées, acteur inconnu ; aucune observation ni validation de
marché déduite de ces valeurs. Les482 nouveaux grains ne sont pas des révisions.

Dans un conteneur Docker `network_mode:none`, sans interfaces hors lo et sans
route externe, exécuter le constructeur readonly :

```sh
PYTHONPATH=/code/backend/src python /code/docs/diagnostics/wb_revision_packet.py \
  /data /code/docs/evidence/R0.8_WB_ARCHIVE_20261104_ANNOTATIONS.json \
  /packet/corpus
```

`/data` est le volume original readonly ; `/packet` est un nouveau volume dédié.
La destination corpus doit être absente. Aucun écrasement, effacement, réseau,
SQL, Bronze ou observation. Le constructeur garde les originaux octet pour
octet, génère les reçus d'acquisition séparés et lie chaque annotation au SHA
complet. Le validateur relit les cellules originales et toute la table, y compris
les lignes hors annotation. Taille ZIP8MiB, décompression64MiB,250000 lignes,
un seul membre CSV, CRC, coordonnées et grain sans doublon ; aucune extraction
sur disque. Le plafond générique5MiB et total50MiB reste intact hors format WB.

Les droits reposent sur la déclaration open data du contexte original et les
[conditions World Bank](https://data.worldbank.org/summary-terms-of-use), consultées
le2026-11-04 : CC BY4.0 par défaut sauf condition spécifique dans les métadonnées,
attribution et absence d'endossement. Citation du producteur incluse dans chaque
reçu ; aucune condition tierce additionnelle relevée sur ces estimations publiées.
Le reçu candidat initial rights_verified=false est conservé comme historique,
la revue des droits et la validation du paquet sont des preuves séparées.

Ce paquet reçu ne suffit pas à R0.8 : restent l'ingestion native avec provenance
ZIP/contextes persistés, la lignée de révision, les manifestes Gold et le rejeu
réel hors réseau avec contre-épreuve de valeur modifiée et Bronze inchangé.
Les prévisions sont une qualification séparée, sur dataset/modèle versionnés.
Aucun tag final ni migration sur la base active autorisé par cette validation.
