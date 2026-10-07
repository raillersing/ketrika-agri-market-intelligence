"use client";

import React from "react";

interface SourceBadgeProps {
  sourceId: string;
  className?: string;
}

const SOURCE_LABELS: Record<string, string> = {
  miasa_odr: "MiASA ODR",
  mincc_ppn: "MinCC PPN",
  wfp_hdx_mdg: "PAM / WFP",
  wb_rtfp_mdg: "Banque Mondiale RTFP",
  instat_nipc: "INSTAT NIPC",
  douanes_stats: "Douanes Malagasy",
  faostat_mdg: "FAOSTAT",
  nasa_power_mdg: "NASA POWER",
  chirps_mdg: "CHIRPS",
  picm: "PICM",
};

export function SourceBadge({ sourceId, className = "" }: SourceBadgeProps) {
  const label = SOURCE_LABELS[sourceId] || sourceId;

  return (
    <span
      title={`Source de données : ${sourceId}`}
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700 ${className}`}
    >
      {label}
    </span>
  );
}
