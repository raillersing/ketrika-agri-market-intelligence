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
  valueKind = null,
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
      className={`glass-card p-5 rounded-2xl flex flex-col justify-between group relative overflow-hidden ${className}`}
    >
      {/* Top subtle highlight gradient line */}
      <div className="absolute top-0 left-0 right-0 h-[1.5px] bg-gradient-to-r from-transparent via-emerald-500/30 to-transparent group-hover:via-emerald-400/60 transition-all duration-500" />

      <div>
        {/* Header: Title & ValueKind */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-medium">
            {title}
          </span>
          {valueKind && <ValueKindBadge kind={valueKind} />}
        </div>

        {/* Main Value Display */}
        <div className="flex items-baseline gap-2 my-1.5">
          <span className="text-3xl font-extrabold tracking-tight text-white group-hover:text-emerald-300 transition-colors">
            {value ?? "—"}
          </span>
          {unit && (
            <span className="text-xs font-mono text-slate-400 font-medium">
              {unit}
            </span>
          )}
        </div>

        {/* Variation / Delta pill */}
        {hasVariation && (
          <div className="flex items-center gap-2 mt-2">
            <span
              className={`inline-flex items-center text-[11px] font-mono font-semibold px-2 py-0.5 rounded-full border ${
                isPositive
                  ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                  : isNegative
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : "bg-slate-800 text-slate-300 border-white/10"
              }`}
            >
              {isPositive && <ArrowUpRight className="w-3 h-3 mr-0.5" />}
              {isNegative && <ArrowDownRight className="w-3 h-3 mr-0.5" />}
              {!isPositive && !isNegative && <Minus className="w-3 h-3 mr-0.5" />}
              {formatPercent(variation)}
            </span>
            <span className="text-[11px] text-slate-400">
              vs ({variationPeriod})
            </span>
          </div>
        )}

        {/* Subtitle / Contextual note */}
        {subtitle && (
          <p className="text-xs text-slate-400 mt-2.5 leading-relaxed">
            {subtitle}
          </p>
        )}
      </div>

      {/* Footer: Sources & Provenance */}
      <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between gap-2 text-xs">
        <div className="flex flex-wrap items-center gap-1.5">
          {sources.slice(0, 2).map((s) => (
            <SourceBadge key={s} sourceId={s} />
          ))}
          {sources.length > 2 && (
            <span className="text-[10px] font-mono text-slate-400">
              +{sources.length - 2}
            </span>
          )}
        </div>
        {observationId ? (
          <ProvenanceLink observationId={observationId} />
        ) : (
          <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400/80 font-mono">
            Provenance non liée
          </span>
        )}
      </div>
    </div>
  );
}
