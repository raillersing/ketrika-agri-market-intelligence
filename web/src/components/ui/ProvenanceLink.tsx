"use client";

import React from "react";
import Link from "next/link";
import { ShieldCheck } from "lucide-react";

interface ProvenanceLinkProps {
  observationId?: string | null;
  className?: string;
  label?: string;
}

export function ProvenanceLink({
  observationId,
  className = "",
  label = "Provenance",
}: ProvenanceLinkProps) {
  if (!observationId) {
    return null;
  }

  return (
    <Link
      href={`/observations/${observationId}`}
      className={`inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:text-emerald-900 hover:underline dark:text-emerald-400 dark:hover:text-emerald-300 ${className}`}
      title="Consulter la traçabilité complète et la preuve d'extraction"
    >
      <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
      <span>{label}</span>
    </Link>
  );
}
