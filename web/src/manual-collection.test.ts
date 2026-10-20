import { describe, expect, it } from "vitest";
import { CollectionReceipt, collectionCounts, collectionStage } from "./lib/manual-collection";

const receipt: CollectionReceipt = {
  request_id: "id", selection: null, source_ids: ["one", "two"], status: "running",
  stage: "bronze:one", outcomes: [], publication: "not_started",
};

describe("durable collection presentation", () => {
  it("labels only the server's actual stage", () => {
    expect(collectionStage(receipt)).toContain("Téléchargement");
    expect(collectionStage({ ...receipt, stage: "silver:one" })).toContain("Vérification");
    expect(collectionStage({ ...receipt, stage: "gold" })).toContain("publication");
  });
  it("does not invent counts for empty or failed collections", () => {
    expect(collectionCounts(receipt)).toEqual({ sources: 0, documents: 0, newDocuments: 0, records: 0 });
    expect(collectionCounts({ ...receipt, outcomes: [{ source_id: "one", status: "failed" }] }).records).toBe(0);
  });
  it("distinguishes new documents and integrated records, not certified quotations", () => {
    expect(collectionCounts({ ...receipt, outcomes: [
      { source_id: "one", status: "success", n_fetched: 2, n_new_artifacts: 1, n_records: 15 },
    ] })).toEqual({ sources: 1, documents: 2, newDocuments: 1, records: 15 });
  });
  it("never labels partial or interrupted collection as complete", () => {
    expect(collectionStage({ ...receipt, status: "partial" })).toContain("partielle");
    expect(collectionStage({ ...receipt, status: "interrupted" })).toContain("interrompue");
  });
});
