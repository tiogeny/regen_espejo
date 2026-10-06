import React from 'react';
import type { ScanPoint } from '../types';

interface FaceTargetOverlayProps {
  activePoint: ScanPoint;
  onSelectPoint?: (point: ScanPoint) => void;
  isScanning?: boolean;
  macroImage?: string;
  onMirrorClick?: (e: React.MouseEvent<HTMLDivElement>) => void;
}

export const FaceTargetOverlay: React.FC<FaceTargetOverlayProps> = ({
  activePoint,
  onSelectPoint,
  isScanning = false,
  macroImage,
  onMirrorClick,
}) => {
  const targetX = activePoint.x;
  const targetY = activePoint.y;

  // Ubicación del círculo de magnificación (cuadrante superior derecho)
  const zoomX = 72;
  const zoomY = 23;

  return (
    <div
      onClick={onMirrorClick}
      className="absolute inset-0 pointer-events-auto z-20 overflow-hidden cursor-crosshair"
      title="Haz clic en cualquier parte de tu rostro para analizar ese punto"
    >
      {/* SVG para dibujar la línea curva guía entre el pómulo y el círculo de zoom */}
      <svg className="w-full h-full absolute inset-0 pointer-events-none">
        <defs>
          <linearGradient id="line-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#e2c694" stopOpacity="0.85" />
            <stop offset="60%" stopColor="#d9b678" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#edd8b3" stopOpacity="0.9" />
          </linearGradient>
        </defs>

        <path
          d={`M ${targetX}% ${targetY}% Q ${(targetX + zoomX) / 2}% ${targetY - 12}%, ${zoomX}% ${zoomY}%`}
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

      {/* Retícula de escaneo sobre el rostro */}
      <div
        className="absolute pointer-events-auto cursor-pointer -translate-x-1/2 -translate-y-1/2 transition-all duration-500 ease-out"
        style={{ left: `${targetX}%`, top: `${targetY}%` }}
        onClick={(e) => {
          e.stopPropagation();
          onSelectPoint && onSelectPoint(activePoint);
        }}
        title="Punto actual de medición dérmica"
      >
        <div className="relative w-12 h-12 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border border-[#e8cda1]/50 animate-ping opacity-60" />
          <div className="absolute inset-1 rounded-full border border-[#edd7b2]/80 animate-pulse-ring" />
          <div className="w-5 h-5 rounded-full bg-[#f1dfbf]/30 border border-[#ffeed1] flex items-center justify-center shadow-[0_0_10px_rgba(241,223,191,0.9)]">
            <div className="w-1.5 h-1.5 rounded-full bg-[#fff6e6] shadow-[0_0_6px_#ffffff]" />
          </div>

          {isScanning && (
            <div className="absolute inset-[-4px] rounded-full border-2 border-t-amber-300 border-r-transparent border-b-transparent border-l-transparent animate-spin" />
          )}
        </div>
      </div>

      {/* Círculo de aumento dermatológico 20x */}
      <div
        className="absolute -translate-x-1/2 -translate-y-1/2 transition-all duration-500 ease-out z-30 pointer-events-none"
        style={{ left: `${zoomX}%`, top: `${zoomY}%` }}
      >
        <div className="relative w-24 h-24 rounded-full p-1 border border-[#ecd5af]/80 shadow-[0_0_20px_rgba(236,213,175,0.35)] backdrop-blur-md bg-neutral-900/70">
          <div className="w-full h-full rounded-full overflow-hidden relative border border-amber-900/40">
            {macroImage ? (
              /* Muestra real de píxeles capturados de tu rostro en cámara */
              <img
                src={macroImage}
                alt="Microscopía dérmica"
                className="w-full h-full object-cover filter contrast-125 saturate-110"
              />
            ) : (
              /* Fallback de textura con simulación de poros */
              <div className="w-full h-full bg-[#bd8363] relative opacity-90 overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-tr from-[#94553b] via-[#c6896c] to-[#e4a889]" />
                <svg className="w-full h-full absolute inset-0 opacity-40" viewBox="0 0 100 100">
                  <pattern id="pores-pattern" width="8" height="8" patternUnits="userSpaceOnUse">
                    <circle cx="2" cy="2" r="0.8" fill="#502416" />
                    <circle cx="6" cy="5" r="0.6" fill="#69301e" />
                    <circle cx="3" cy="7" r="0.4" fill="#38190f" />
                  </pattern>
                  <rect width="100" height="100" fill="url(#pores-pattern)" />
                </svg>
              </div>
            )}

            {/* Efecto de lente cóncava */}
            <div className="absolute inset-0 rounded-full shadow-[inset_0_0_12px_rgba(0,0,0,0.7)] pointer-events-none" />

            {/* Retícula en cruz microscópica */}
            <div className="absolute inset-0 flex items-center justify-center opacity-30 pointer-events-none">
              <div className="w-full h-[0.5px] bg-[#ffe4be]" />
              <div className="h-full w-[0.5px] bg-[#ffe4be] absolute" />
            </div>
          </div>

          <div className="absolute -bottom-1 right-1 px-1.5 py-0.5 rounded-full bg-black/85 border border-[#ecd5af]/60 text-[8.5px] font-mono text-[#edd7b2]">
            20x
          </div>
        </div>
      </div>
    </div>
  );
};
