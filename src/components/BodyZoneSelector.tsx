import React from 'react';
import { Sparkles, Droplet, Wind, Shield, CloudSun, Compass, User, Scissors, Smile, Hand } from 'lucide-react';
import type { BodyZone, ZoneAnalysis } from '../types';

interface BodyZoneSelectorProps {
  currentZone: BodyZone;
  onSelectZone: (zone: BodyZone) => void;
  zoneData: ZoneAnalysis;
}

const ZONES: { id: BodyZone; label: string; icon: React.ReactNode; desc: string }[] = [
  { id: 'rostro', label: 'Piel Facial', icon: <User className="w-4 h-4" />, desc: 'Pómulos, Zona T & Manto ácido' },
  { id: 'cabello', label: 'Cabello & Folículo', icon: <Scissors className="w-4 h-4" />, desc: 'Porosidad, Densidad & Ungurahui' },
  { id: 'sonrisa', label: 'Sonrisa & Labios', icon: <Smile className="w-4 h-4" />, desc: 'Esmalte, Arcilla Chaco & Menta' },
  { id: 'cuerpo', label: 'Manos & Cuerpo', icon: <Hand className="w-4 h-4" />, desc: 'Barrera lipídica & Murumuru' },
];

export const BodyZoneSelector: React.FC<BodyZoneSelectorProps> = ({
  currentZone,
  onSelectZone,
  zoneData,
}) => {
  const getIcon = (type: string) => {
    switch (type) {
      case 'droplet': return <Droplet className="w-3.5 h-3.5 text-[#e4c28d]" />;
      case 'wind': return <Wind className="w-3.5 h-3.5 text-[#deb579]" />;
      case 'shield': return <Shield className="w-3.5 h-3.5 text-[#99c996]" />;
      default: return <Sparkles className="w-3.5 h-3.5 text-[#99c996]" />;
    }
  };

  return (
    <div className="w-72 max-w-[22vw] flex flex-col justify-between h-[86vh] py-1 select-none pointer-events-auto">
      {/* 1. Selector de Zonas Anatómicas */}
      <div className="glass-panel rounded-2xl p-3 border border-[#dfc699]/30 shadow-xl space-y-2">
        <div className="flex items-center justify-between pb-1.5 border-b border-neutral-800">
          <div className="flex items-center gap-1.5">
            <Compass className="w-3.5 h-3.5 text-[#d9b77d]" />
            <span className="text-[10px] tracking-[0.2em] uppercase font-mono text-[#d9b77d] font-semibold">
              MAPA ANATÓMICO
            </span>
          </div>
          <span className="text-[9px] text-neutral-400 font-mono">IA SENSOR</span>
        </div>

        <div className="space-y-1">
          {ZONES.map((z) => {
            const isActive = currentZone === z.id;
            return (
              <button
                key={z.id}
                onClick={() => onSelectZone(z.id)}
                className={`w-full text-left p-2 rounded-xl transition-all flex items-center gap-2.5 ${
                  isActive
                    ? 'bg-gradient-to-r from-[#d9b77d]/25 to-amber-950/30 border border-[#d9b77d]/50 shadow-md'
                    : 'bg-black/30 border border-neutral-800/60 hover:bg-neutral-800/40 text-neutral-300'
                }`}
              >
                <div
                  className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    isActive ? 'bg-[#d9b77d] text-neutral-950' : 'bg-neutral-800 text-neutral-400'
                  }`}
                >
                  {z.icon}
                </div>
                <div className="overflow-hidden">
                  <span className={`block text-xs font-medium truncate ${isActive ? 'text-amber-200' : 'text-neutral-200'}`}>
                    {z.label}
                  </span>
                  <span className="block text-[9.5px] text-neutral-400 truncate font-light">
                    {z.desc}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Diagnóstico & Métricas de la Zona Actual */}
      <div className="glass-panel rounded-2xl p-3 border border-[#dfc699]/30 shadow-xl space-y-2.5">
        <div>
          <span className="block text-[9px] tracking-[0.2em] uppercase font-mono text-[#d4c5a9] opacity-80">
            {zoneData.typeLabel}
          </span>
          <h3 className="text-sm font-medium text-neutral-100 tracking-wide mt-0.5">
            {zoneData.typeName}
          </h3>
          <p className="text-[10px] text-neutral-400 font-light">
            {zoneData.subtitle}
          </p>
        </div>

        {/* Barras de métricas específicas */}
        <div className="space-y-2 pt-1 border-t border-neutral-800">
          {zoneData.metrics.map((m) => (
            <div key={m.id} className="space-y-0.5">
              <div className="flex items-center justify-between text-[10.5px]">
                <div className="flex items-center gap-1.5 text-neutral-300">
                  {getIcon(m.iconType)}
                  <span>{m.label}</span>
                </div>
                <span className="font-mono text-amber-200 font-semibold">{m.displayValue}</span>
              </div>
              <div className="w-full h-1.5 bg-neutral-800 rounded-full overflow-hidden border border-neutral-700/40">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${m.value}%`,
                    backgroundColor: m.color,
                    boxShadow: `0 0 6px ${m.color}`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 3. Sensor Ambiental de Contexto (Perú) */}
      <div className="glass-panel-subtle rounded-2xl p-2.5 border border-[#dfc699]/20 shadow-lg text-[10.5px] space-y-1">
        <div className="flex items-center justify-between text-neutral-300">
          <div className="flex items-center gap-1.5">
            <CloudSun className="w-3.5 h-3.5 text-amber-300" />
            <span className="font-medium text-neutral-200">Bio-Clima Perú</span>
          </div>
          <span className="text-[9px] text-emerald-400 font-mono">EN VIVO</span>
        </div>
        <div className="grid grid-cols-3 gap-1 pt-1 text-center font-mono text-[9.5px]">
          <div className="p-1 rounded-lg bg-black/40 border border-neutral-800">
            <span className="block text-neutral-400 text-[8.5px]">HUMEDAD</span>
            <span className="text-amber-200 font-semibold">78%</span>
          </div>
          <div className="p-1 rounded-lg bg-black/40 border border-neutral-800">
            <span className="block text-neutral-400 text-[8.5px]">ÍNDICE UV</span>
            <span className="text-amber-200 font-semibold">6.2 (Mod)</span>
          </div>
          <div className="p-1 rounded-lg bg-black/40 border border-neutral-800">
            <span className="block text-neutral-400 text-[8.5px]">TEMP</span>
            <span className="text-amber-200 font-semibold">22°C</span>
          </div>
        </div>
      </div>
    </div>
  );
};
