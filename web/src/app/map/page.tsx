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

type LocationMeta = {
  location_id: string;
  pcode: string;
  name: string;
  admin_level: number;
};

function MapContent() {
  const searchParams = useSearchParams();
  const product = searchParams.get("product") || DEFAULT_PRODUCT;
  const [rows, setRows] = useState<TerritorialPrice[]>([]);
  const [nationalPrice, setNationalPrice] = useState<TerritorialPrice | null>(null);
  const [locations, setLocations] = useState<LocationMeta[]>([]);
  const [selectedPcode, setSelectedPcode] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setRows([]);
    setNationalPrice(null);

    async function load() {
      try {
        if (isLegacyDQProduct(product)) throw new Error(DQ_SELECTION_MESSAGE);
        const [regRes, natRes, locRes] = await Promise.all([
          fetch(`/api/v1/prices/latest?${new URLSearchParams({ product, level: "1" })}`, {
            credentials: "include",
            signal: controller.signal,
          }),
          fetch(`/api/v1/prices/latest?${new URLSearchParams({ product, level: "0" })}`, {
            credentials: "include",
            signal: controller.signal,
          }).catch(() => null),
          fetch(`/api/v1/locations?level=1`, {
            credentials: "include",
            signal: controller.signal,
          }).catch(() => null),
        ]);

        if (!regRes.ok) throw new Error(`Les prix par territoire sont indisponibles (HTTP ${regRes.status}).`);
        const regData: TerritorialPrice[] = await regRes.json();
        const natData: TerritorialPrice[] = natRes?.ok ? await natRes.json() : [];
        const locData: LocationMeta[] = locRes?.ok ? await locRes.json() : [];

        if (!controller.signal.aborted) {
          setRows(regData);
          setNationalPrice(natData[0] || null);
          setLocations(locData);
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

  // Build the dictionary of regional prices for the ChoroplethMap
  const regionPricesMap: Record<string, RegionPriceData> = {};

  // Initialize with official locations (23 regions of Madagascar)
  // Use national parity benchmark as default price if specific local survey is absent
  for (const loc of locations) {
    if (loc.admin_level === 1) {
      regionPricesMap[loc.pcode] = {
        pcode: loc.pcode,
        name: loc.name,
        price: nationalPrice?.median_price ?? null,
        unit: nationalPrice?.unit || "kg",
        valueKind: nationalPrice?.value_kind || undefined,
        sourceId: nationalPrice ? (nationalPrice.sources?.[0] || "parite_nationale") : undefined,
      };
    }
  }

  // Overlay specific regional survey prices if available
  for (const row of rows) {
    regionPricesMap[row.location_pcode] = {
      pcode: row.location_pcode,
      name: row.location_name || row.location_pcode,
      price: row.median_price,
      unit: row.unit,
      valueKind: row.value_kind,
      sourceId: row.sources?.[0],
    };
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold text-foreground">
          <MapPin aria-hidden="true" className="h-6 w-6 shrink-0 text-primary-readable" />
          Prix par territoire et découpage régional
        </h1>
        <p className="text-sm leading-6 text-muted-foreground">
          Répartition des cours vivriers sur les 23 régions de Madagascar. Les estimations économétriques nationales et les relevés directs sont traçables avec leur niveau administratif.
        </p>
      </header>

      {/* National Benchmark Card if available */}
      {nationalPrice && (
        <section className="rounded-2xl border border-primary/20 bg-primary/5 p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-wider font-semibold text-primary-readable flex items-center gap-2">
              <Compass className="w-4 h-4" />
              Référence nationale de parité (Niveau Admin 0 — Madagascar)
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-foreground">
              {formatPrice(nationalPrice.median_price, nationalPrice.unit, nationalPrice.currency === "MGA" ? "Ar" : nationalPrice.currency)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Dernière mise à jour : {formatMonthYear(nationalPrice.month)} · Modèle : Parité d’importation / Modèle vivrier national (DGD / BFM / Pink Sheet).
            </p>
          </div>
          <div className="flex items-center gap-2">
            <ValueKindBadge kind={nationalPrice.value_kind} />
            {nationalPrice.sources?.map((s) => (
              <SourceBadge key={s} sourceId={s} />
            ))}
          </div>
        </section>
      )}

      {/* Regional Visualizer Map Component */}
      <section aria-labelledby="map-availability" className="space-y-3">
        <h2 id="map-availability" className="text-lg font-medium text-foreground flex items-center gap-2">
          <Compass className="w-5 h-5 text-primary-readable" />
          Carte interactive des régions de Madagascar
        </h2>
        <ChoroplethMap
          regionPrices={regionPricesMap}
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
          Chargement des points territoriaux…
        </p>
      ) : (
        !error && (
          <section className="rounded-xl border border-border bg-card p-5">
            <h2 className="text-lg font-medium">Relevés régionaux directs disponibles</h2>
            <p className="my-3 text-sm leading-6 text-muted-foreground">
              Les dates et les sources correspondent aux enquêtes régionales enregistrées (ex. WFP / RTFP / INSTAT). Pour les denrées sans enquête directe locale, la référence de parité nationale s’applique.
            </p>

            {!rows.length ? (
              <p role="status" className="py-6 text-sm text-muted-foreground">
                Aucune enquête de marché locale directe au niveau régional pour ce produit. Consultez la référence nationale ci-dessus ou sélectionnez un autre produit (ex. Riz blanc local).
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
                          {row.currency === "MGA"
                            ? formatPrice(row.median_price, row.unit)
                            : `${row.median_price} ${row.currency}/${row.unit}`}
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
