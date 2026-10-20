export interface CollectionOutcome {
  source_id: string;
  status: string;
  run_id?: string | null;
  n_fetched?: number | null;
  n_new_artifacts?: number | null;
  n_records?: number | null;
}

export interface CollectionReceipt {
  request_id: string;
  selection: string | null;
  status: "running" | "succeeded" | "partial" | "failed" | "interrupted";
  stage: string;
  source_ids: string[];
  outcomes: CollectionOutcome[];
  publication: string;
}

export function collectionStage(receipt: CollectionReceipt): string {
  const [stage, source] = receipt.stage.split(":");
  if (receipt.status === "interrupted") return "Collecte interrompue — résultat incomplet, aucune reprise automatique";
  if (receipt.status === "partial") return "Collecte partielle — consultez les résultats et la publication";
  if (receipt.status === "failed") return "Collecte non aboutie — aucune réussite à supposer";
  if (receipt.status === "succeeded") return "Collecte et recalcul terminés";
  if (stage === "bronze") return `Téléchargement des documents publics : ${source}`;
  if (stage === "silver") return `Vérification et intégration : ${source}`;
  if (stage === "gold") return "Contrôle de provenance et publication des indicateurs";
  return "Préparation de la collecte des sources autorisées";
}

export function collectionCounts(receipt: CollectionReceipt) {
  const completed = receipt.outcomes.filter(item => item.status === "success");
  return {
    sources: completed.length,
    documents: completed.reduce((sum, item) => sum + (item.n_fetched ?? 0), 0),
    newDocuments: completed.reduce((sum, item) => sum + (item.n_new_artifacts ?? 0), 0),
    records: completed.reduce((sum, item) => sum + (item.n_records ?? 0), 0),
  };
}
