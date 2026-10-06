import React, { useState } from 'react';
import { ArrowRight, Beaker } from 'lucide-react';
import type { BioProduct } from '../types';

interface BioproductCardProps {
  products: BioProduct[];
  currentIndex: number;
  onSelectProduct: (index: number) => void;
  onOpenDispenser: (product: BioProduct) => void;
}

export const BioproductCard: React.FC<BioproductCardProps> = ({
  products,
  currentIndex,
  onSelectProduct,
  onOpenDispenser,
}) => {
  const currentProduct = products[currentIndex] || products[0];
  const [selectedIngredient, setSelectedIngredient] = useState<string | null>(null);

  const size = 96;
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  let accumulatedPercent = 0;

  const handleNext = () => {
    onSelectProduct((currentIndex + 1) % products.length);
    setSelectedIngredient(null);
  };

  const activeIngObj = currentProduct.ingredients.find((i) => i.id === selectedIngredient);

  return (
    <div className="relative w-80 glass-panel rounded-3xl p-5 select-none shadow-[0_8px_32px_rgba(0,0,0,0.45)] border border-[#e1cd9f]/30">
      <div className="mb-3">
        <span className="block text-[10px] tracking-[0.25em] text-[#d4c5a9] font-medium uppercase opacity-85">
          {currentProduct.title}
        </span>
        <h2 className="text-xl font-light text-neutral-100 tracking-wide mt-0.5">
          {currentProduct.name}
        </h2>
        <p className="text-xs text-[#c9b794] font-light mt-0.5">
          {currentProduct.tagline}
        </p>
      </div>

      <div className="flex items-center gap-4 py-1">
        <div className="relative w-24 h-24 flex-shrink-0 flex items-center justify-center">
          <svg className="w-full h-full -rotate-90" viewBox={`0 0 ${size} ${size}`}>
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke="#212623"
              strokeWidth={strokeWidth}
            />

            {currentProduct.ingredients.map((ing) => {
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
                  className="transition-all duration-700 ease-out cursor-pointer hover:opacity-90"
                  onClick={() => setSelectedIngredient(selectedIngredient === ing.id ? null : ing.id)}
                />
              );
            })}
          </svg>

          <div className="absolute inset-0 m-auto w-12 h-12 rounded-full bg-[#1e231e] border border-[#d8be8a]/50 flex items-center justify-center shadow-inner">
            <svg
              viewBox="0 0 24 24"
              className="w-5 h-5 stroke-[#e5cca0] fill-none"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 2C7 8 4 12 4 16a8 8 0 0 0 16 0c0-4-3-8-8-14z" />
              <path d="M12 9v13" />
            </svg>
          </div>
        </div>

        <div className="flex-1 space-y-1.5">
          {currentProduct.ingredients.map((ing) => (
            <div
              key={ing.id}
              onClick={() => setSelectedIngredient(selectedIngredient === ing.id ? null : ing.id)}
              className={`flex items-center justify-between text-xs cursor-pointer rounded px-1.5 py-0.5 transition-all ${
                selectedIngredient === ing.id
                  ? 'bg-amber-400/15 border border-amber-300/30'
                  : 'hover:bg-neutral-800/40'
              }`}
            >
              <div className="flex items-center gap-1.5 overflow-hidden">
                <span
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: ing.color }}
                />
                <span className="text-[11px] text-neutral-200 truncate font-light">
                  {ing.name}
                </span>
              </div>
              <span className="text-[11px] text-[#dec39b] font-mono font-medium pl-2">
                {ing.percentage}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {activeIngObj && (
        <div className="mt-3 p-2.5 rounded-xl bg-black/50 border border-amber-400/30 text-[11px] space-y-1 animate-fadeIn">
          <div className="flex items-center justify-between text-amber-200">
            <span className="font-semibold">{activeIngObj.name}</span>
            <span className="italic opacity-80 text-[10px]">{activeIngObj.scientificName}</span>
          </div>
          <p className="text-neutral-300 text-[10.5px] leading-tight">{activeIngObj.benefit}</p>
          <div className="text-[9.5px] text-[#c9b794] pt-0.5">
            📍 {activeIngObj.origin}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mt-4 pt-2 border-t border-neutral-700/30">
        <div className="flex items-center gap-1.5 pl-1">
          {products.map((p, idx) => (
            <button
              key={p.id}
              onClick={() => onSelectProduct(idx)}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                idx === currentIndex
                  ? 'w-4 bg-[#dec39b]'
                  : 'w-1.5 bg-neutral-600 hover:bg-neutral-400'
              }`}
              aria-label={`Ver ${p.name}`}
            />
          ))}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onOpenDispenser(currentProduct)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] bg-[#d9b77d]/20 hover:bg-[#d9b77d]/35 border border-[#d9b77d]/50 text-[#edd2aa] transition-all"
            title="Generar orden de biofabricación"
          >
            <Beaker className="w-3 h-3" />
            <span>Formular</span>
          </button>

          <button
            onClick={handleNext}
            className="w-7 h-7 rounded-full bg-neutral-800/80 hover:bg-[#d9b77d]/30 border border-[#d9b77d]/40 flex items-center justify-center text-[#ebd1a8] transition-all hover:scale-105"
            aria-label="Siguiente bioproducto"
          >
            <ArrowRight className="w-3.5 h-3.5 stroke-[2]" />
          </button>
        </div>
      </div>
    </div>
  );
};
