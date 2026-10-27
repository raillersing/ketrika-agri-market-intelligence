"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useTheme } from "@/components/theme/ThemeProvider";
import { CHART_PALETTES } from "@/lib/theme";
import { withCalendarGaps } from "@/lib/market-overview";
import { escapeHtml } from "@/lib/reading";
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
  modelRequested?: string;
  modelEffective?: string;
  isBaseline?: boolean;
  isCalibrated?: boolean;
  calibrationSampleSize?: number;
  status?: string;
  fallbackReason?: string;
  horizon?: number;
  datasetFingerprint?: string;
}

interface PriceChartProps {
  title?: string;
  data: PriceDataPoint[];
  productName?: string;
  unit?: string;
  currency?: string;
  onPointClick?: (point: PriceDataPoint) => void;
  className?: string;
}

export function PriceChart({
  title = "Évolution du prix médian",
  data,
  productName = "Riz blanc local",
  unit = "kg",
  currency = "MGA",
  onPointClick,
  className = "",
}: PriceChartProps) {
  const { theme } = useTheme();
  const palette = CHART_PALETTES[theme];
  const currencyLabel = currency === "MGA" ? "Ar" : currency;
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className={`h-88 flex items-center justify-center glass-panel rounded-2xl text-muted-foreground text-xs font-mono ${className}`}>
        Initialisation du visualiseur analytique...
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className={`h-88 flex items-center justify-center glass-panel rounded-2xl text-muted-foreground text-xs font-mono ${className}`}>
        Aucune donnée de prix disponible pour la sélection actuelle.
      </div>
    );
  }

  const sortedData = [...data].sort((a, b) => a.month.localeCompare(b.month));
  const chartRows = withCalendarGaps(sortedData);
  const categories = chartRows.map((d) => d ? formatMonthYear(d.month) : "Période sans données");
  const medianPrices = chartRows.map((d) => d ? d.medianPrice : null);

  const hasBand = sortedData.some((d) => (d.p10Price ?? d.minPrice) !== undefined);
  const bandBase = chartRows.map((d) => d ? d.p10Price ?? d.minPrice ?? d.medianPrice : null);
  const bandRange = chartRows.map((d) => {
    if (!d) return null;
    const high = d.p90Price ?? d.maxPrice ?? d.medianPrice;
    const low = d.p10Price ?? d.minPrice ?? d.medianPrice;
    return Math.max(0, high - low);
  });

  const option = {
    backgroundColor: "transparent",
    title: {
      text: title,
      subtext: `${productName} • ${currencyLabel}/${unit}`,
      left: "16",
      top: "16",
      textStyle: { fontSize: 13, fontWeight: "700", color: palette.text, fontFamily: "inherit" },
      subtextStyle: { fontSize: 11, color: palette.muted, fontFamily: "inherit" },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: palette.tooltip,
      borderColor: palette.border,
      borderWidth: 1,
      padding: [12, 14],
      textStyle: { color: palette.text, fontSize: 12 },
      extraCssText: "box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5); backdrop-filter: blur(12px); border-radius: 12px;",
      formatter: (params: any) => {
        const idx = params[0]?.dataIndex;
        if (idx === undefined || !chartRows[idx]) return "";
        const item = chartRows[idx];
        const isForecast = item.valueKind === "forecast";
        const kindInfo = getValueKindInfo(item.valueKind);
        const sourceLabel = item.sourceId ? `Source : ${item.sourceId}` : "";

        return `
          <div style="font-family: inherit; font-size: 11px;">
            <div style="font-weight: 700; margin-bottom: 6px; color: ${isForecast ? palette.forecast : palette.primary}; font-size: 12px;">
              ${escapeHtml(formatMonthYear(item.month))} ${isForecast && item.horizon ? `(Horizon h=${item.horizon})` : ''}
            </div>
            <div style="margin-bottom: 4px; display: flex; justify-content: space-between; gap: 12px;">
              <span style="color: ${palette.muted};">${isForecast ? 'Prévision (p50) :' : 'Prix médian :'}</span>
              <strong style="color: ${palette.text}; font-family: monospace;">${escapeHtml(formatPrice(item.medianPrice, unit, currencyLabel))}</strong>
            </div>
            ${item.p10Price !== undefined && item.p90Price !== undefined && item.p10Price !== null && item.p90Price !== null ? `
            <div style="color: ${palette.text}; margin-bottom: 4px; display: flex; justify-content: space-between; gap: 12px;">
              <span style="color: ${palette.muted};">Intervalle [p10, p90] :</span>
              <span style="font-family: monospace;">${escapeHtml(formatPrice(item.p10Price, unit, currencyLabel))} – ${escapeHtml(formatPrice(item.p90Price, unit, currencyLabel))}</span>
            </div>` : item.minPrice != null && item.maxPrice != null ? `
            <div style="color: ${palette.muted}; margin-bottom: 4px; display: flex; justify-content: space-between; gap: 12px;">
              <span>Fourchette (Min - Max) :</span>
              <span style="font-family: monospace;">${escapeHtml(formatPrice(item.minPrice, unit, currencyLabel))} – ${escapeHtml(formatPrice(item.maxPrice, unit, currencyLabel))}</span>
            </div>` : ""}
            ${isForecast && item.modelEffective ? `
            <div style="margin-top: 6px; padding-top: 6px; border-top: 1px solid ${palette.border}; font-size: 10px; color: ${palette.text};">
              <div>Modèle : <strong style="color: ${palette.text};">${escapeHtml(item.modelEffective)}${item.isBaseline ? ' (Baseline)' : ''}</strong></div>
              ${item.fallbackReason ? `<div style="color: ${palette.warning};">Repli : ${escapeHtml(item.fallbackReason)}</div>` : ''}
              <div style="color: ${item.isCalibrated ? palette.primary : palette.warning};">
                ${item.isCalibrated ? `Calibration déclarée par le modèle (N=${item.calibrationSampleSize ?? 'non renseigné'})` : 'Calibration non déclarée dans cette réponse'}
              </div>
            </div>` : ''}
            <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid ${palette.border}; display: flex; align-items: center; justify-content: space-between; gap: 10px;">
              <span style="color: ${isForecast ? palette.forecast : palette.imputed}; font-size: 10px;">● ${escapeHtml(kindInfo.label)}</span>
              ${sourceLabel ? `<span style="color: ${palette.muted}; font-size: 10px; font-family: monospace;">${escapeHtml(sourceLabel)}</span>` : ""}
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
      axisLine: { lineStyle: { color: palette.border } },
      axisTick: { show: false },
      axisLabel: { color: palette.muted, fontSize: 11, fontFamily: "inherit" },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: palette.border, type: "dashed" } },
      axisLabel: {
        color: palette.muted,
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
              areaStyle: { color: palette.band },
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
          color: palette.primary,
          borderColor: palette.primary,
          borderWidth: 2,
        },
        lineStyle: {
          width: 3,
          color: palette.primary,
          shadowColor: "transparent",
          shadowBlur: 0,
        },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: palette.area },
              { offset: 1, color: "transparent" },
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
