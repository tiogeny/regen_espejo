import React, { useState } from 'react';
import { Droplet, Wind, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';
import type { SkinMetrics } from '../types';

interface SkinMetricsCardProps {
  metrics: SkinMetrics;
  onUpdateMetric?: (key: keyof SkinMetrics, value: number) => void;
  interactive?: boolean;
}

export const SkinMetricsCard: React.FC<SkinMetricsCardProps> = ({
  metrics,
  onUpdateMetric,
  interactive = true,
}) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="flex flex-col text-right items-end select-none font-sans text-neutral-200">
      <div className="mb-3 text-right">
        <span className="block text-[11px] tracking-[0.25em] text-[#d4c5a9] font-medium uppercase opacity-90">
          PIEL
        </span>
        <span className="text-xl font-light tracking-wide text-neutral-100">
          {metrics.skinType}
        </span>
      </div>

      <div className="w-56 space-y-2.5">
        <div className="flex items-center justify-between text-xs gap-2">
          <div className="flex items-center gap-1.5 text-[#e2c79a]">
            <Droplet className="w-3.5 h-3.5 stroke-[1.5]" />
            <span className="text-[11px] text-neutral-300 font-normal">Hidratación</span>
          </div>

          <div className="flex items-center gap-2 flex-1 justify-end">
            <div className="relative w-24 h-1.5 bg-neutral-800/80 rounded-full overflow-hidden border border-neutral-700/50">
              <div
                className="h-full bg-gradient-to-r from-[#c59d5f] to-[#e4c28d] rounded-full transition-all duration-500 shadow-[0_0_8px_rgba(228,194,141,0.6)]"
                style={{ width: `${metrics.hydration}%` }}
              />
              <div
                className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 bg-[#f5e6cf] rounded-full border border-amber-900 shadow-md transition-all duration-500 -ml-1"
                style={{ left: `${metrics.hydration}%` }}
              />
            </div>
            <span className="w-8 text-right text-[11px] text-[#e8cfab] font-medium font-mono">
              {metrics.hydration}%
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs gap-2">
          <div className="flex items-center gap-1.5 text-[#e2c79a]">
            <Wind className="w-3.5 h-3.5 stroke-[1.5]" />
            <span className="text-[11px] text-neutral-300 font-normal">Oleosidad</span>
          </div>

          <div className="flex items-center gap-2 flex-1 justify-end">
            <div className="relative w-24 h-1.5 bg-neutral-800/80 rounded-full overflow-hidden border border-neutral-700/50">
              <div
                className="h-full bg-gradient-to-r from-[#b3884b] to-[#deb579] rounded-full transition-all duration-500 shadow-[0_0_8px_rgba(222,181,121,0.6)]"
                style={{ width: `${metrics.sebum}%` }}
              />
              <div
                className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 bg-[#f5e6cf] rounded-full border border-amber-900 shadow-md transition-all duration-500 -ml-1"
                style={{ left: `${metrics.sebum}%` }}
              />
            </div>
            <span className="w-8 text-right text-[11px] text-[#e8cfab] font-medium font-mono">
              {metrics.sebum}%
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs gap-2">
          <div className="flex items-center gap-1.5 text-[#a8c99c]">
            <Sparkles className="w-3.5 h-3.5 stroke-[1.5]" />
            <span className="text-[11px] text-neutral-300 font-normal">pH</span>
          </div>

          <div className="flex items-center gap-2 flex-1 justify-end">
            <div className="relative w-24 h-1.5 bg-neutral-800/80 rounded-full overflow-hidden border border-neutral-700/50">
              <div
                className="h-full bg-gradient-to-r from-[#6e9c6b] to-[#99c996] rounded-full transition-all duration-500 shadow-[0_0_8px_rgba(153,201,150,0.6)]"
                style={{ width: `${Math.min(100, Math.max(0, ((metrics.ph - 3.5) / 5) * 100))}%` }}
              />
              <div
                className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 bg-[#d4ecd2] rounded-full border border-emerald-950 shadow-md transition-all duration-500 -ml-1"
                style={{ left: `${Math.min(100, Math.max(0, ((metrics.ph - 3.5) / 5) * 100))}%` }}
              />
            </div>
            <span className="w-8 text-right text-[11px] text-[#bde0b9] font-medium font-mono">
              {metrics.ph.toFixed(1)}
            </span>
          </div>
        </div>
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-2.5 flex items-center justify-center text-neutral-400 hover:text-amber-200 transition-colors p-1"
        aria-label="Más detalles dermatológicos"
      >
        {expanded ? (
          <ChevronUp className="w-4 h-4 stroke-[1.5] text-[#d4c5a9]" />
        ) : (
          <ChevronDown className="w-4 h-4 stroke-[1.5] text-[#d4c5a9]" />
        )}
      </button>

      {expanded && (
        <div className="mt-2 w-56 p-3 rounded-lg glass-panel-subtle text-[11px] text-left border border-neutral-700/40 animate-fadeIn">
          <div className="flex justify-between py-0.5">
            <span className="text-neutral-400">Zona analizada:</span>
            <span className="text-neutral-200 font-medium">{metrics.zone}</span>
          </div>
          <div className="flex justify-between py-0.5">
            <span className="text-neutral-400">Poros visibles:</span>
            <span className="text-neutral-200 font-medium">{metrics.pores}%</span>
          </div>
          <div className="flex justify-between py-0.5">
            <span className="text-neutral-400">Elasticidad:</span>
            <span className="text-neutral-200 font-medium">{metrics.elasticity}%</span>
          </div>
          {interactive && onUpdateMetric && (
            <div className="mt-2 pt-2 border-t border-neutral-700/40 space-y-1.5">
              <span className="text-[10px] text-amber-200/70 block uppercase tracking-wider">Ajuste manual:</span>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-neutral-400">Hidratación</span>
                <input
                  type="range"
                  min="10"
                  max="90"
                  value={metrics.hydration}
                  onChange={(e) => onUpdateMetric('hydration', Number(e.target.value))}
                  className="w-20 accent-amber-400 h-1"
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-neutral-400">Oleosidad</span>
                <input
                  type="range"
                  min="10"
                  max="90"
                  value={metrics.sebum}
                  onChange={(e) => onUpdateMetric('sebum', Number(e.target.value))}
                  className="w-20 accent-amber-400 h-1"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
