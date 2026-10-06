import React from 'react';
import type { ScanPoint } from '../types';

interface FaceTargetOverlayProps {
  activePoint: ScanPoint;
  onSelectPoint?: (point: ScanPoint) => void;
  isScanning?: boolean;
}

export const FaceTargetOverlay: React.FC<FaceTargetOverlayProps> = ({
  activePoint,
  onSelectPoint,
  isScanning = true,
}) => {
  const targetX = activePoint.x;
  const targetY = activePoint.y;

  const zoomX = 68;
  const zoomY = 26;

  return (
    <div className="absolute inset-0 pointer-events-none z-20 overflow-hidden">
      <svg className="w-full h-full absolute inset-0">
        <defs>
          <linearGradient id="line-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#e2c694" stopOpacity="0.8" />
            <stop offset="70%" stopColor="#d9b678" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#edd8b3" stopOpacity="0.9" />
          </linearGradient>
        </defs>

        <path
          d={`M ${targetX}% ${targetY}% Q ${(targetX + zoomX) / 2}% ${targetY - 8}%, ${zoomX}% ${zoomY}%`}
          fill="none"
          stroke="url(#line-grad)"
          strokeWidth="1.2"
          strokeDasharray="3 3"
          className="transition-all duration-700 ease-out"
        />

        <circle
          cx={`${zoomX}%`}
          cy={`${zoomY}%`}
          r="2.5"
          className="fill-[#ecd2a9] drop-shadow-[0_0_6px_rgba(236,210,169,0.9)]"
        />
      </svg>

      <div
        className="absolute pointer-events-auto cursor-pointer -translate-x-1/2 -translate-y-1/2 transition-all duration-700 ease-out"
        style={{ left: `${targetX}%`, top: `${targetY}%` }}
        onClick={() => onSelectPoint && onSelectPoint(activePoint)}
        title="Punto de análisis dérmico"
      >
        <div className="relative w-14 h-14 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border border-[#e8cda1]/40 animate-ping opacity-60" />
          <div className="absolute inset-1 rounded-full border border-[#edd7b2]/70 animate-pulse-ring" />
          <div className="w-6 h-6 rounded-full bg-[#f1dfbf]/25 border border-[#ffeed1] flex items-center justify-center shadow-[0_0_12px_rgba(241,223,191,0.8)]">
            <div className="w-2 h-2 rounded-full bg-[#fff6e6] shadow-[0_0_8px_#ffffff]" />
          </div>

          {isScanning && (
            <div className="absolute inset-0 rounded-full border-t border-[#ffe6ba] animate-radar opacity-80" />
          )}
        </div>
      </div>

      <div
        className="absolute -translate-x-1/2 -translate-y-1/2 transition-all duration-500 ease-out z-30"
        style={{ left: `${zoomX}%`, top: `${zoomY}%` }}
      >
        <div className="relative w-28 h-28 rounded-full p-1 border border-[#ecd5af]/80 shadow-[0_0_24px_rgba(236,213,175,0.4)] backdrop-blur-sm bg-neutral-900/60">
          <div className="w-full h-full rounded-full overflow-hidden relative border border-amber-900/40">
            <div className="w-full h-full bg-[#bd8363] relative opacity-90 mix-blend-screen overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-tr from-[#94553b] via-[#c6896c] to-[#e4a889]" />
              <svg className="w-full h-full absolute inset-0 opacity-45" viewBox="0 0 100 100">
                <pattern id="pores-pattern" width="8" height="8" patternUnits="userSpaceOnUse">
                  <circle cx="2" cy="2" r="0.8" fill="#502416" />
                  <circle cx="6" cy="5" r="0.6" fill="#69301e" />
                  <circle cx="3" cy="7" r="0.4" fill="#38190f" />
                </pattern>
                <rect width="100" height="100" fill="url(#pores-pattern)" />
              </svg>
              <div className="absolute inset-0 bg-gradient-to-b from-white/25 via-transparent to-black/30" />
            </div>

            <div className="absolute inset-0 rounded-full shadow-[inset_0_0_15px_rgba(0,0,0,0.6)]" />

            <div className="absolute inset-0 flex items-center justify-center opacity-30 pointer-events-none">
              <div className="w-full h-[0.5px] bg-[#ffe4be]" />
              <div className="h-full w-[0.5px] bg-[#ffe4be] absolute" />
            </div>
          </div>

          <div className="absolute -bottom-1 right-2 px-1.5 py-0.5 rounded-full bg-black/80 border border-[#ecd5af]/50 text-[9px] font-mono text-[#edd7b2]">
            20x
          </div>
        </div>
      </div>
    </div>
  );
};
