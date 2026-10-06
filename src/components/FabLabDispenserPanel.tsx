import React, { useState } from 'react';
import { Cpu, Beaker } from 'lucide-react';
import type { BioProduct, TankLevel } from '../types';

interface FabLabDispenserPanelProps {
  product: BioProduct;
  tanks: TankLevel[];
  onOpenDispenser: (prod: BioProduct) => void;
}

export const FabLabDispenserPanel: React.FC<FabLabDispenserPanelProps> = ({
  product,
  tanks,
  onOpenDispenser,
}) => {
  const [selectedIngredient, setSelectedIngredient] = useState<string | null>(null);

  const size = 84;
  const strokeWidth = 9;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  let accumulatedPercent = 0;
  const activeIngObj = product.ingredients.find((i) => i.id === selectedIngredient);

  return (
    <div className="w-72 max-w-[22vw] flex flex-col justify-between h-[86vh] py-1 select-none pointer-events-auto">
      {/* 1. Tarjeta del Bioproducto Personalizado */}
      <div className="glass-panel rounded-2xl p-3 border border-[#dfc699]/30 shadow-xl space-y-2">
        <div>
          <span className="block text-[9px] tracking-[0.2em] uppercase font-mono text-[#d4c5a9] opacity-80">
            {product.title}
          </span>
          <div className="flex items-baseline justify-between mt-0.5">
            <h2 className="text-sm font-semibold text-neutral-100 tracking-wide">
              {product.name}
            </h2>
            <span className="text-[10px] text-amber-200/90 font-mono">
              pH {product.phTarget}
            </span>
          </div>
          <p className="text-[10.5px] text-[#c9b794] font-light">
            {product.tagline}
          </p>
        </div>

        {/* Donut Chart SVG con lista de activos peruanos */}
        <div className="flex items-center gap-3 pt-1">
          <div className="relative w-20 h-20 flex-shrink-0 flex items-center justify-center">
            <svg className="w-full h-full -rotate-90" viewBox={`0 0 ${size} ${size}`}>
              <circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke="#212623"
                strokeWidth={strokeWidth}
              />

              {product.ingredients.map((ing) => {
                const dashLength = (ing.percentage / 100) * circumference;
                const dashOffset = -((accumulatedPercent / 100) * circumference);
                accumulatedPercent += ing.percentage;

                return (
                  <circle
                    key={ing.id}
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={ing.color}
                    strokeWidth={strokeWidth}
                    strokeDasharray={`${dashLength} ${circumference - dashLength}`}
                    strokeDashoffset={dashOffset}
                    className="transition-all duration-700 cursor-pointer hover:opacity-85"
                    onClick={() => setSelectedIngredient(selectedIngredient === ing.id ? null : ing.id)}
                  />
                );
              })}
            </svg>

            {/* Núcleo central con hoja botánica */}
            <div className="absolute inset-0 m-auto w-10 h-10 rounded-full bg-[#1e231e] border border-[#d8be8a]/50 flex items-center justify-center shadow-inner">
              <svg
                viewBox="0 0 24 24"
                className="w-4 h-4 stroke-[#e5cca0] fill-none"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 2C7 8 4 12 4 16a8 8 0 0 0 16 0c0-4-3-8-8-14z" />
                <path d="M12 9v13" />
              </svg>
            </div>
          </div>

          {/* Lista de ingredientes y porcentajes */}
          <div className="flex-1 space-y-1">
            {product.ingredients.map((ing) => (
              <div
                key={ing.id}
                onClick={() => setSelectedIngredient(selectedIngredient === ing.id ? null : ing.id)}
                className={`flex items-center justify-between text-[10.5px] cursor-pointer rounded px-1.5 py-0.5 transition-all ${
                  selectedIngredient === ing.id
                    ? 'bg-amber-400/20 border border-amber-300/40'
                    : 'hover:bg-neutral-800/40'
                }`}
              >
                <div className="flex items-center gap-1.5 overflow-hidden">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: ing.color }} />
                  <span className="text-neutral-200 truncate font-light text-[10px]">{ing.name}</span>
                </div>
                <span className="text-[#dec39b] font-mono font-medium pl-1 text-[10px]">
                  {ing.percentage}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Detalle emergente de ingrediente */}
        {activeIngObj && (
          <div className="p-2 rounded-xl bg-black/60 border border-amber-400/30 text-[10px] space-y-0.5 animate-fadeIn">
            <div className="flex items-center justify-between text-amber-200">
              <span className="font-semibold">{activeIngObj.name}</span>
              <span className="italic opacity-75 text-[9px]">{activeIngObj.scientificName}</span>
            </div>
            <p className="text-neutral-300 text-[9.5px] leading-tight">{activeIngObj.benefit}</p>
            <div className="text-[8.5px] text-[#c9b794] pt-0.5">
              📍 {activeIngObj.origin}
            </div>
          </div>
        )}
      </div>

      {/* 2. Consola de Biofabricación Fab Lab Perú */}
      <div className="glass-panel rounded-2xl p-3 border border-[#dfc699]/30 shadow-xl space-y-2">
        <div className="flex items-center justify-between pb-1.5 border-b border-neutral-800">
          <div className="flex items-center gap-1.5 text-neutral-300">
            <Cpu className="w-3.5 h-3.5 text-[#d9b77d]" />
            <span className="text-[10px] tracking-[0.15em] uppercase font-mono text-[#d9b77d] font-semibold">
              FAB LAB DISPENSER
            </span>
          </div>
          <span className="flex items-center gap-1 text-[9px] text-emerald-400 font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
            ONLINE
          </span>
        </div>

        {/* Tanques de extractos nativos peruanos */}
        <div className="space-y-1.5">
          <span className="text-[9px] text-neutral-400 uppercase font-mono tracking-wider block">
            Nivel de tanques de reserva (Perú):
          </span>
          <div className="grid grid-cols-2 gap-1.5">
            {tanks.slice(0, 4).map((tank) => (
              <div
                key={tank.id}
                className="p-1.5 rounded-xl bg-black/40 border border-neutral-800 text-[9.5px]"
              >
                <div className="flex items-center justify-between text-neutral-300">
                  <span className="truncate">{tank.name}</span>
                  <span className="font-mono text-amber-200">{tank.level}%</span>
                </div>
                <div className="w-full h-1 bg-neutral-800 rounded-full mt-1 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${tank.level}%`, backgroundColor: tank.color }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Botón principal de formular */}
        <button
          onClick={() => onOpenDispenser(product)}
          className="w-full mt-2 py-2 px-3 rounded-xl bg-gradient-to-r from-[#d9b77d] via-[#e5cca0] to-[#c79d5e] text-neutral-950 font-semibold text-xs flex items-center justify-center gap-2 shadow-lg hover:brightness-105 active:scale-95 transition-all"
        >
          <Beaker className="w-4 h-4 text-neutral-900" />
          <span>Dispensar en Fab Lab</span>
        </button>
      </div>
    </div>
  );
};
