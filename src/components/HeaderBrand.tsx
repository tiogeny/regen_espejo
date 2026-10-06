import React from 'react';

export const HeaderBrand: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center select-none pt-2 pointer-events-none">
      {/* Símbolo geométrico botánico REGEN */}
      <div className="relative w-8 h-8 flex items-center justify-center mb-1">
        <svg
          viewBox="0 0 40 40"
          className="w-full h-full stroke-[#e7cca2] fill-none drop-shadow-[0_0_8px_rgba(231,204,162,0.6)]"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {/* Hojas entrelazadas / Semilla germinando */}
          <path d="M20 6 C24 12, 28 17, 28 23 C28 28.5, 24.4 33, 20 34 C15.6 33, 12 28.5, 12 23 C12 17, 16 12, 20 6 Z" />
          <path d="M20 12 C21.5 16, 24 19, 27 21" />
          <path d="M20 17 C18.5 20, 16 22, 13 23" />
          <circle cx="20" cy="22" r="1.5" className="fill-[#e7cca2]" />
        </svg>
      </div>

      {/* Tipografía REGEN */}
      <h1 className="text-sm tracking-[0.45em] uppercase text-[#e7cca2] font-light pl-[0.45em] drop-shadow-[0_0_12px_rgba(231,204,162,0.4)]">
        R E G E N
      </h1>
    </div>
  );
};
