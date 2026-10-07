"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { formatMonthYear, formatPrice, getValueKindInfo, type ValueKind } from "@/lib/formatters";

// Dynamically import ReactECharts to prevent SSR window reference errors
const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

export interface PriceDataPoint {
  month: string; // YYYY-MM-01
  medianPrice: number;
  minPrice?: number | null;
  maxPrice?: number | null;
  p10Price?: number | null;
  p90Price?: number | null;
  valueKind?: ValueKind | string;
  sourceId?: string;
  observationId?: string;
}

interface PriceChartProps {
  title?: string;
  data: PriceDataPoint[];
  productName?: string;
  unit?: string;
  onPointClick?: (point: PriceDataPoint) => void;
  className?: string;
}

export function PriceChart({
  title = "Évolution du prix médian",
  data,
  productName = "Riz blanc local",
  unit = "kg",
  onPointClick,
  className = "",
}: PriceChartProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className={`h-80 flex items-center justify-center bg-card border border-border rounded-lg text-muted-foreground text-sm ${className}`}>
        Chargement du graphique...
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className={`h-80 flex items-center justify-center bg-card border border-border rounded-lg text-muted-foreground text-sm ${className}`}>
        Aucune donnée de prix disponible pour ces filtres.
      </div>
    );
  }

  const sortedData = [...data].sort((a, b) => a.month.localeCompare(b.month));
  const categories = sortedData.map((d) => formatMonthYear(d.month));
  const medianPrices = sortedData.map((d) => d.medianPrice);

  // Band lower and upper bounds (using p10/p90 or min/max)
  const hasBand = sortedData.some((d) => (d.p10Price ?? d.minPrice) !== undefined);
  const bandBase = sortedData.map((d) => d.p10Price ?? d.minPrice ?? d.medianPrice);
  const bandRange = sortedData.map((d) => {
    const high = d.p90Price ?? d.maxPrice ?? d.medianPrice;
    const low = d.p10Price ?? d.minPrice ?? d.medianPrice;
    return Math.max(0, high - low);
  });

  const option = {
    title: {
      text: title,
      subtext: `${productName} (Ar/${unit})`,
      left: "2%",
      top: "2%",
      textStyle: { fontSize: 14, fontWeight: "600", color: "#1e293b" },
      subtextStyle: { fontSize: 12, color: "#64748b" },
    },
    tooltip: {
      trigger: "axis",
      formatter: (params: any) => {
        const idx = params[0]?.dataIndex;
        if (idx === undefined || !sortedData[idx]) return "";
        const item = sortedData[idx];
        const kindInfo = getValueKindInfo(item.valueKind);
        const sourceLabel = item.sourceId ? `Source: ${item.sourceId}` : "";

        return `
          <div style="font-family: inherit; font-size: 12px; padding: 4px;">
            <div style="font-weight: 600; margin-bottom: 4px; color: #0f172a;">${formatMonthYear(item.month)}</div>
            <div style="margin-bottom: 2px;">
              <strong>Prix médian :</strong> ${formatPrice(item.medianPrice, unit)}
            </div>
            ${item.minPrice && item.maxPrice ? `<div style="color: #64748b; margin-bottom: 2px;">Fourchette : ${formatPrice(item.minPrice, unit)} – ${formatPrice(item.maxPrice, unit)}</div>` : ""}
            <div style="margin-top: 4px; display: flex; align-items: center; gap: 6px;">
              <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: #059669;"></span>
              <span>Statut : <strong>${kindInfo.label}</strong></span>
            </div>
            ${sourceLabel ? `<div style="color: #64748b; font-size: 11px; margin-top: 2px;">${sourceLabel}</div>` : ""}
          </div>
        `;
      },
    },
    grid: {
      top: "18%",
      left: "4%",
      right: "4%",
      bottom: "10%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: categories,
      boundaryGap: false,
      axisLine: { lineStyle: { color: "#cbd5e1" } },
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisLabel: {
        color: "#64748b",
        formatter: (val: number) => `${val.toLocaleString("fr-FR")} Ar`,
      },
      splitLine: { lineStyle: { color: "#f1f5f9" } },
    },
    series: [
      // Transparent baseline for the band
      ...(hasBand
        ? [
            {
              name: "Plage basse",
              type: "line",
              data: bandBase,
              lineStyle: { opacity: 0 },
              stack: "confidence-band",
              symbol: "none",
            },
            {
              name: "Intervalle (P10-P90 / Min-Max)",
              type: "line",
              data: bandRange,
              lineStyle: { opacity: 0 },
              areaStyle: { color: "rgba(16, 185, 129, 0.15)" },
              stack: "confidence-band",
              symbol: "none",
            },
          ]
        : []),
      // Primary median price line
      {
        name: "Prix médian",
        type: "line",
        data: medianPrices,
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        itemStyle: { color: "#059669" },
        lineStyle: { width: 3, color: "#059669" },
      },
    ],
  };

  const onEvents = {
    click: (params: any) => {
      const idx = params?.dataIndex;
      if (idx !== undefined && sortedData[idx] && onPointClick) {
        onPointClick(sortedData[idx]);
      }
    },
  };

  return (
    <div className={`bg-card p-4 rounded-lg border border-border shadow-sm ${className}`}>
      <ReactECharts
        option={option}
        style={{ height: "340px", width: "100%" }}
        onEvents={onEvents}
      />
    </div>
  );
}
