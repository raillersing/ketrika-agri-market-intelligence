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
      <div className={`h-88 flex items-center justify-center glass-panel rounded-2xl text-slate-400 text-xs font-mono ${className}`}>
        Initialisation du visualiseur analytique...
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className={`h-88 flex items-center justify-center glass-panel rounded-2xl text-slate-400 text-xs font-mono ${className}`}>
        Aucune donnée de prix disponible pour la sélection actuelle.
      </div>
    );
  }

  const sortedData = [...data].sort((a, b) => a.month.localeCompare(b.month));
  const categories = sortedData.map((d) => formatMonthYear(d.month));
  const medianPrices = sortedData.map((d) => d.medianPrice);

  const hasBand = sortedData.some((d) => (d.p10Price ?? d.minPrice) !== undefined);
  const bandBase = sortedData.map((d) => d.p10Price ?? d.minPrice ?? d.medianPrice);
  const bandRange = sortedData.map((d) => {
    const high = d.p90Price ?? d.maxPrice ?? d.medianPrice;
    const low = d.p10Price ?? d.minPrice ?? d.medianPrice;
    return Math.max(0, high - low);
  });

  const option = {
    backgroundColor: "transparent",
    title: {
      text: title,
      subtext: `${productName} • En Ariary (Ar/${unit})`,
      left: "16",
      top: "16",
      textStyle: { fontSize: 13, fontWeight: "700", color: "#f8fafc", fontFamily: "inherit" },
      subtextStyle: { fontSize: 11, color: "#94a3b8", fontFamily: "inherit" },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(15, 23, 42, 0.95)",
      borderColor: "rgba(255, 255, 255, 0.1)",
      borderWidth: 1,
      padding: [12, 14],
      textStyle: { color: "#f8fafc", fontSize: 12 },
      extraCssText: "box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5); backdrop-filter: blur(12px); border-radius: 12px;",
      formatter: (params: any) => {
        const idx = params[0]?.dataIndex;
        if (idx === undefined || !sortedData[idx]) return "";
        const item = sortedData[idx];
        const kindInfo = getValueKindInfo(item.valueKind);
        const sourceLabel = item.sourceId ? `Source : ${item.sourceId}` : "";

        return `
          <div style="font-family: inherit; font-size: 11px;">
            <div style="font-weight: 700; margin-bottom: 6px; color: #34d399; font-size: 12px;">${formatMonthYear(item.month)}</div>
            <div style="margin-bottom: 4px; display: flex; justify-content: space-between; gap: 12px;">
              <span style="color: #94a3b8;">Prix médian :</span>
              <strong style="color: #ffffff; font-family: monospace;">${formatPrice(item.medianPrice, unit)}</strong>
            </div>
            ${item.minPrice && item.maxPrice ? `
            <div style="color: #64748b; margin-bottom: 4px; display: flex; justify-content: space-between; gap: 12px;">
              <span>Fourchette (Min - Max) :</span>
              <span style="font-family: monospace;">${formatPrice(item.minPrice, unit)} – ${formatPrice(item.maxPrice, unit)}</span>
            </div>` : ""}
            <div style="margin-top: 8px; pt-2; border-top: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: space-between; gap: 10px;">
              <span style="color: #38bdf8; font-size: 10px;">● ${kindInfo.label}</span>
              ${sourceLabel ? `<span style="color: #94a3b8; font-size: 10px; font-family: monospace;">${sourceLabel}</span>` : ""}
            </div>
          </div>
        `;
      },
    },
    grid: {
      left: "45",
      right: "25",
      top: "75",
      bottom: "35",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: categories,
      boundaryGap: false,
      axisLine: { lineStyle: { color: "rgba(255, 255, 255, 0.1)" } },
      axisTick: { show: false },
      axisLabel: { color: "#94a3b8", fontSize: 11, fontFamily: "inherit" },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "rgba(255, 255, 255, 0.05)", type: "dashed" } },
      axisLabel: {
        color: "#94a3b8",
        fontSize: 10,
        fontFamily: "monospace",
        formatter: (val: number) => `${val.toLocaleString("fr-FR")}`,
      },
    },
    series: [
      ...(hasBand
        ? [
            {
              name: "Base fourchette",
              type: "line",
              data: bandBase,
              lineStyle: { opacity: 0 },
              stack: "confidence-band",
              symbol: "none",
            },
            {
              name: "Intervalle de variation",
              type: "line",
              data: bandRange,
              lineStyle: { opacity: 0 },
              areaStyle: { color: "rgba(16, 185, 129, 0.08)" },
              stack: "confidence-band",
              symbol: "none",
            },
          ]
        : []),
      {
        name: "Prix médian",
        type: "line",
        data: medianPrices,
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        itemStyle: {
          color: "#10b981",
          borderColor: "#064e3b",
          borderWidth: 2,
        },
        lineStyle: {
          width: 3,
          color: "#10b981",
          shadowColor: "rgba(16, 185, 129, 0.4)",
          shadowBlur: 10,
        },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(16, 185, 129, 0.3)" },
              { offset: 1, color: "rgba(16, 185, 129, 0.0)" },
            ],
          },
        },
      },
    ],
  };

  return (
    <div className={`glass-card p-2 rounded-2xl relative overflow-hidden ${className}`}>
      <ReactECharts
        option={option}
        style={{ height: "340px", width: "100%" }}
        onEvents={{
          click: (params: any) => {
            if (params.dataIndex !== undefined && sortedData[params.dataIndex] && onPointClick) {
              onPointClick(sortedData[params.dataIndex]);
            }
          },
        }}
      />
    </div>
  );
}
