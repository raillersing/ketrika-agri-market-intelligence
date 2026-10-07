"use client";

import React from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { formatPercent, type ValueKind } from "@/lib/formatters";
import { ValueKindBadge } from "./ValueKindBadge";
import { SourceBadge } from "./SourceBadge";
import { ProvenanceLink } from "./ProvenanceLink";

export interface KpiCardProps {
  title: string;
  value: string | number | null | undefined;
  unit?: string;
  variation?: number | null; // e.g. 0.052 for +5.2%
  variationPeriod?: string; // e.g. "m/m" or "a/a"
  valueKind?: ValueKind | string | null;
  sources?: string[];
  observationId?: string | null;
  subtitle?: string;
  className?: string;
}

export function KpiCard({
  title,
  value,
  unit,
  variation,
  variationPeriod = "m/m",
  valueKind = "observed",
  sources = [],
  observationId,
  subtitle,
  className = "",
}: KpiCardProps) {
  const hasVariation = variation !== null && variation !== undefined && !isNaN(variation);
  const isPositive = hasVariation && variation > 0;
  const isNegative = hasVariation && variation < 0;

  return (
    <div
      className={`bg-card text-card-foreground p-5 rounded-lg border border-border shadow-sm flex flex-col justify-between hover:border-emerald-500/40 transition-colors ${className}`}
    >
      <div>
        <div className="flex items-start justify-between gap-2 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {title}
          </span>
          {valueKind && <ValueKindBadge kind={valueKind} />}
        </div>

        <div className="flex items-baseline gap-2 my-1">
          <span className="text-2xl font-bold tracking-tight text-foreground">
            {value ?? "—"}
          </span>
          {unit && (
            <span className="text-sm font-medium text-muted-foreground">
              {unit}
            </span>
          )}
        </div>

        {hasVariation && (
          <div className="flex items-center gap-1.5 mt-2">
            <span
              className={`inline-flex items-center text-xs font-semibold px-1.5 py-0.5 rounded ${
                isPositive
                  ? "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                  : isNegative
                  ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              {isPositive && <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" />}
              {isNegative && <ArrowDownRight className="w-3.5 h-3.5 mr-0.5" />}
              {!isPositive && !isNegative && <Minus className="w-3.5 h-3.5 mr-0.5" />}
              {formatPercent(variation)}
            </span>
            <span className="text-xs text-muted-foreground">
              vs période préc. ({variationPeriod})
            </span>
          </div>
        )}

        {subtitle && (
          <p className="text-xs text-muted-foreground mt-2">{subtitle}</p>
        )}
      </div>

      <div className="mt-4 pt-3 border-t border-border flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <div className="flex flex-wrap gap-1">
          {sources.slice(0, 2).map((s) => (
            <SourceBadge key={s} sourceId={s} />
          ))}
          {sources.length > 2 && (
            <span className="text-xs text-muted-foreground">
              +{sources.length - 2}
            </span>
          )}
        </div>
        {observationId && <ProvenanceLink observationId={observationId} />}
      </div>
    </div>
  );
}
