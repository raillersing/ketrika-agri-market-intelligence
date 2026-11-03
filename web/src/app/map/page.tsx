"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Compass, MapPin, RefreshCw } from "lucide-react";
import { DEFAULT_PRODUCT } from "@/lib/market-overview";
import { DQ_SELECTION_MESSAGE, isLegacyDQProduct } from "@/lib/market-filters";
import { formatMonthYear, formatPrice } from "@/lib/formatters";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";
import { SourceBadge } from "@/components/ui/SourceBadge";
import { ChoroplethMap, type RegionPriceData } from "@/components/maps/ChoroplethMap";

type TerritorialPrice = {
  product_code: string;
  location_pcode: string;
  location_name: string | null;
  month: string;
  median_price: number;
  currency: string;
  unit: string;
  value_kind: string;
  sources: string[];
};

function MapContent() {
  const searchParams = useSearchParams();
  const product = searchParams.get("product") || DEFAULT_PRODUCT;
  const [rows, setRows] = useState<TerritorialPrice[]>([]);
  const [nationalPrices, setNationalPrices] = useState<TerritorialPrice[]>([]);
  const [selectedPcode, setSelectedPcode] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setRows([]);
    setNationalPrices([]);

    async function load() {
      try {
        if (isLegacyDQProduct(product)) throw new Error(DQ_SELECTION_MESSAGE);
        const [regRes, natRes] = await Promise.all([
          fetch(`/api/v1/prices/latest?${new URLSearchParams({ product, level: "1" })}`, {
            credentials: "include",
            signal: controller.signal,
          }),
          fetch(`/api/v1/prices/latest?${new URLSearchParams({ product, level: "0" })}`, {
            credentials: "include",
            signal: controller.signal,
          }).catch(() => null),
        ]);

        if (!regRes.ok) throw new Error(`Les prix par territoire sont indisponibles (HTTP ${regRes.status}).`);
        const regData: TerritorialPrice[] = await regRes.json();
        const natData: TerritorialPrice[] = natRes?.ok ? await natRes.json() : [];

        if (!controller.signal.aborted) {
          setRows(regData);
          setNationalPrices(natData);
        }
      } catch (failure) {
        if (!controller.signal.aborted) {
          setError(failure instanceof Error ? failure.message : "Les prix par territoire sont indisponibles.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void load();
    return () => controller.abort();
  }, [product]);

  const regionPoints: RegionPriceData[] = rows.map((row) => ({
      pcode: row.location_pcode,
      name: row.location_name || row.location_pcode,
      price: row.median_price,
      unit: row.unit,
      currency: row.currency,
      valueKind: row.value_kind,
      sources: row.sources || [],
  }));

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold text-foreground">
          <MapPin aria-hidden="true" className="h-6 w-6 shrink-0 text-primary-readable" />
          Prix par territoire et découpage régional
        </h1>
        <p className="text-sm leading-6 text-muted-foreground">
          Les points sont affichés à leur niveau enregistré. Un point national ne remplace pas une mesure régionale.
        </p>
      </header>

      {/* National Benchmark Card if available */}
      {nationalPrices.map((nationalPrice, index) => (
        <section key={`${nationalPrice.location_pcode}-${index}`} aria-label="Point national disponible" className="rounded-2xl border border-primary/20 bg-primary/5 p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-wider font-semibold text-primary-readable flex items-center gap-2">
              <Compass className="w-4 h-4" />
              Point national de la sélection
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-foreground">
              {formatPrice(nationalPrice.median_price, nationalPrice.unit || "Unité non renseignée", nationalPrice.currency === "MGA" ? "Ar" : nationalPrice.currency || "Devise non renseignée")}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Période enregistrée : {formatMonthYear(nationalPrice.month)}. Ce point ne décrit pas les prix de chaque région.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <ValueKindBadge kind={nationalPrice.value_kind} />
            {nationalPrice.sources?.length ? nationalPrice.sources.map((s) => (
              <SourceBadge key={s} sourceId={s} />
            )) : <span className="text-xs text-muted-foreground">Source non renseignée</span>}
          </div>
        </section>
      ))}

      {/* Regional Visualizer Map Component */}
      <section aria-labelledby="map-availability" className="space-y-3">
        <h2 id="map-availability" className="text-lg font-medium text-foreground flex items-center gap-2">
          <Compass className="w-5 h-5 text-primary-readable" />
          Carte géographique en préparation
        </h2>
        <ChoroplethMap
          regionPrices={regionPoints}
          selectedPcode={selectedPcode}
          onRegionSelect={(pcode) => setSelectedPcode(pcode === selectedPcode ? undefined : pcode)}
          className="shadow-sm"
        />
      </section>

      {error && (
        <p role="alert" className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </p>
      )}

      {loading ? (
        <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
          <RefreshCw aria-hidden="true" className="h-4 w-4 animate-spin" />
          Chargement des prix par territoire…
        </p>
      ) : (
        !error && (
          <section className="rounded-xl border border-border bg-card p-5">
            <h2 className="text-lg font-medium">Derniers points par zone</h2>
            <p className="my-3 text-sm leading-6 text-muted-foreground">
              Consultez la période, la nature et les sources de chaque point régional disponible. Aucune valeur nationale n’est reportée sur une région sans donnée.
            </p>

            {!rows.length ? (
              <p role="status" className="py-6 text-sm text-muted-foreground">
                Aucun point régional enregistré pour ce produit. Un éventuel point national est présenté séparément.
              </p>
            ) : (
              <div className="relative overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Prix par territoire, périodes et sources pour {product}</caption>
                  <thead className="text-muted-foreground">
                    <tr>
                      {["Zone", "Période", "Prix", "Nature", "Source", "Historique"].map((title) => (
                        <th key={title} scope="col" className="p-3 font-medium">
                          {title}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, index) => (
                      <tr key={`${row.location_pcode}-${index}`} className="border-t border-border">
                        <th scope="row" className="p-3 font-medium">
                          {row.location_name || row.location_pcode || "Zone non renseignée"}
                        </th>
                        <td className="whitespace-nowrap p-3">{formatMonthYear(row.month)}</td>
                        <td className="whitespace-nowrap p-3">
                          {formatPrice(row.median_price, row.unit || "Unité non renseignée", row.currency === "MGA" ? "Ar" : row.currency || "Devise non renseignée")}
                        </td>
                        <td className="p-3">
                          <ValueKindBadge kind={row.value_kind} />
                        </td>
                        <td className="p-3">
                          {row.sources?.length ? (
                            row.sources.map((source) => <SourceBadge key={source} sourceId={source} />)
                          ) : (
                            "Source non renseignée"
                          )}
                        </td>
                        <td className="p-3">
                          <Link
                            className="inline-flex min-h-[44px] items-center rounded px-2 text-primary-readable underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
                            href={`/prices?${new URLSearchParams({
                              product,
                              ...(row.location_pcode ? { region: row.location_pcode } : {}),
                            })}`}
                          >
                            Voir la série
                            <span className="sr-only"> — {row.location_name || row.location_pcode}</span>
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )
      )}
    </div>
  );
}

export default function MapPage() {
  return (
    <React.Suspense fallback={<p role="status">Chargement de la vue territoriale…</p>}>
      <MapContent />
    </React.Suspense>
  );
}
