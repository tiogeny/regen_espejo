import React from 'react';
import { HeaderBrand } from './HeaderBrand';
import { FaceTargetOverlay } from './FaceTargetOverlay';
import { SkinMetricsCard } from './SkinMetricsCard';
import { BioproductCard } from './BioproductCard';
import type { SkinMetrics, BioProduct, ScanPoint } from '../types';

interface MirrorFrameProps {
  metrics: SkinMetrics;
  products: BioProduct[];
  currentProductIndex: number;
  onSelectProduct: (index: number) => void;
  onOpenDispenser: (product: BioProduct) => void;
  onUpdateMetric: (key: keyof SkinMetrics, value: number) => void;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  useWebcam: boolean;
  activeScanPoint: ScanPoint;
  onSelectScanPoint: (pt: ScanPoint) => void;
  lightTone: 'warm' | 'neutral' | 'cool' | 'off';
  lightBrightness: number;
  macroImage?: string;
  isScanning?: boolean;
  onMirrorClick?: (xPercent: number, yPercent: number) => void;
}

export const MirrorFrame: React.FC<MirrorFrameProps> = ({
  metrics,
  products,
  currentProductIndex,
  onSelectProduct,
  onOpenDispenser,
  onUpdateMetric,
  videoRef,
  useWebcam,
  activeScanPoint,
  onSelectScanPoint,
  lightTone,
  lightBrightness,
  macroImage,
  isScanning = false,
  onMirrorClick,
}) => {
  const getGlowStyles = () => {
    if (lightTone === 'off') return 'border-neutral-700 shadow-none';
    const alpha = (lightBrightness / 100).toFixed(2);
    if (lightTone === 'warm') {
      return `border-[#f5dfb8] shadow-[0_0_${Math.round(lightBrightness * 0.7)}px_rgba(245,215,150,${alpha}),inset_0_0_${Math.round(lightBrightness * 0.25)}px_rgba(255,230,180,0.35)]`;
    }
    if (lightTone === 'cool') {
      return `border-[#e3f0fc] shadow-[0_0_${Math.round(lightBrightness * 0.7)}px_rgba(200,230,255,${alpha}),inset_0_0_${Math.round(lightBrightness * 0.25)}px_rgba(220,240,255,0.35)]`;
    }
    return `border-[#fffaee] shadow-[0_0_${Math.round(lightBrightness * 0.7)}px_rgba(255,250,230,${alpha}),inset_0_0_${Math.round(lightBrightness * 0.25)}px_rgba(255,250,240,0.35)]`;
  };

  const handleContainerClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!onMirrorClick) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    // Evitar clics extremos fuera del radio facial
    if (x >= 20 && x <= 80 && y >= 20 && y <= 80) {
      onMirrorClick(Math.round(x * 10) / 10, Math.round(y * 10) / 10);
    }
  };

  return (
    <div className="relative flex flex-col items-center justify-center select-none">
      {/* Contenedor circular con escala dinámica basada en viewport height */}
      <div className="relative w-[min(74vh,580px)] h-[min(74vh,580px)] aspect-square rounded-full p-2.5 flex items-center justify-center">
        {/* Bisel metálico exterior */}
        <div className="absolute inset-0 rounded-full border-[8px] border-[#383126] shadow-[0_15px_40px_rgba(0,0,0,0.85),inset_0_2px_4px_rgba(255,255,255,0.15)] bg-gradient-to-br from-[#2a241b] via-[#1c1813] to-[#3b3223]" />

        {/* Aro perimetral de iluminación LED */}
        <div
          className={`absolute inset-1.5 rounded-full border-[4px] transition-all duration-700 ${getGlowStyles()}`}
        />

        {/* Cristal del espejo */}
        <div
          onClick={handleContainerClick}
          className="relative w-full h-full rounded-full overflow-hidden bg-neutral-950 flex items-center justify-center border border-white/10 shadow-inner cursor-crosshair"
        >
          {/* Transmisión de la cámara web (invertida en espejo) */}
          {useWebcam ? (
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="absolute inset-0 w-full h-full object-cover -scale-x-100 filter brightness-105 contrast-105 saturate-[1.05]"
            />
          ) : (
            <div className="absolute inset-0 w-full h-full">
              <img
                src="https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=1000&q=80"
                alt="Reflejo Smart Mirror"
                className="w-full h-full object-cover -scale-x-100 filter brightness-95 contrast-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-black/40 pointer-events-none" />
            </div>
          )}

          {/* Viñeta circular suave */}
          <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_center,transparent_45%,rgba(0,0,0,0.65)_95%)] pointer-events-none" />

          {/* Retícula de escaneo interactiva */}
          <FaceTargetOverlay
            activePoint={activeScanPoint}
            onSelectPoint={onSelectScanPoint}
            isScanning={isScanning}
            macroImage={macroImage}
          />

          {/* Capa HUD holográfica */}
          <div className="absolute inset-0 p-5 flex flex-col justify-between pointer-events-none">
            {/* Header: REGEN */}
            <div className="w-full flex justify-center">
              <HeaderBrand />
            </div>

            {/* Panel de métricas (arriba a la derecha) */}
            <div className="flex justify-end pr-2 pointer-events-auto">
              <SkinMetricsCard
                metrics={metrics}
                onUpdateMetric={onUpdateMetric}
              />
            </div>

            {/* Panel Bioproducto (abajo a la derecha) */}
            <div className="flex justify-end pr-1 pb-1 pointer-events-auto">
              <BioproductCard
                products={products}
                currentIndex={currentProductIndex}
                onSelectProduct={onSelectProduct}
                onOpenDispenser={onOpenDispenser}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Soporte vertical decorativo minimalista */}
      <div className="w-4 h-6 bg-gradient-to-b from-[#2a241b] to-[#1a1612] border-x border-[#524430] shadow-md -mt-0.5" />
      <div className="w-24 h-2 rounded-full bg-gradient-to-r from-[#201b14] via-[#3d3324] to-[#201b14] border border-[#524430] shadow-lg" />
    </div>
  );
};
