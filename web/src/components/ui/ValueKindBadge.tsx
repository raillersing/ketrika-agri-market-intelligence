"use client";

import React from "react";
import { getValueKindInfo, type ValueKind } from "../../lib/formatters";

interface ValueKindBadgeProps {
  kind: ValueKind | string | null | undefined;
  className?: string;
  showTooltip?: boolean;
}

export function ValueKindBadge({
  kind,
  className = "",
  showTooltip = true,
}: ValueKindBadgeProps) {
  const info = getValueKindInfo(kind);

  return (
    <span
      title={showTooltip ? info.description : undefined}
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${info.badgeClass} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-70" />
      {info.label}
    </span>
  );
}
