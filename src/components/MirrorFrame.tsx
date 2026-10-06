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
}) => {
  const getGlowStyles = () => {
    if (lightTone === 'off') return 'border-neutral-700 shadow-none';
    const alpha = (lightBrightness / 100).toFixed(2);
    if (lightTone === 'warm') {
      return `border-[#f5dfb8] shadow-[0_0_${Math.round(lightBrightness * 0.9)}px_rgba(245,215,150,${alpha}),inset_0_0_${Math.round(lightBrightness * 0.3)}px_rgba(255,230,180,0.4)]`;
    }
    if (lightTone === 'cool') {
      return `border-[#e3f0fc] shadow-[0_0_${Math.round(lightBrightness * 0.9)}px_rgba(200,230,255,${alpha}),inset_0_0_${Math.round(lightBrightness * 0.3)}px_rgba(220,240,255,0.4)]`;
    }
    return `border-[#fffaee] shadow-[0_0_${Math.round(lightBrightness * 0.9)}px_rgba(255,250,230,${alpha}),inset_0_0_${Math.round(lightBrightness * 0.3)}px_rgba(255,250,240,0.4)]`;
  };

  return (
    <div className="relative flex flex-col items-center justify-center p-4 min-h-[92vh]">
      <div className="relative w-[680px] h-[680px] max-w-[94vw] max-h-[94vw] rounded-full p-3 flex items-center justify-center">
        <div className="absolute inset-0 rounded-full border-[10px] border-[#383126] shadow-[0_20px_50px_rgba(0,0,0,0.8),inset_0_2px_4px_rgba(255,255,255,0.15)] bg-gradient-to-br from-[#2a241b] via-[#1c1813] to-[#3b3223]" />

        <div
          className={`absolute inset-2 rounded-full border-[5px] transition-all duration-700 ${getGlowStyles()}`}
        />

        <div className="relative w-full h-full rounded-full overflow-hidden bg-neutral-950 flex items-center justify-center border border-white/10 shadow-inner">
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
                src="https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=1200&q=80"
                alt="Reflejo Smart Mirror"
                className="w-full h-full object-cover -scale-x-100 filter brightness-95 contrast-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-black/40 pointer-events-none" />
            </div>
          )}

          <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_center,transparent_40%,rgba(0,0,0,0.65)_95%)] pointer-events-none" />

          <FaceTargetOverlay
            activePoint={activeScanPoint}
            onSelectPoint={onSelectScanPoint}
            isScanning={true}
          />

          <div className="absolute inset-0 p-8 flex flex-col justify-between pointer-events-none">
            <div className="w-full flex justify-center">
              <HeaderBrand />
            </div>

            <div className="flex justify-end pr-2 pt-2 pointer-events-auto">
              <SkinMetricsCard
                metrics={metrics}
                onUpdateMetric={onUpdateMetric}
              />
            </div>

            <div className="flex justify-end pb-3 pr-2 pointer-events-auto">
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

      <div className="w-6 h-12 bg-gradient-to-b from-[#2a241b] to-[#1a1612] border-x border-[#524430] shadow-xl -mt-1" />
      <div className="w-32 h-3 rounded-full bg-gradient-to-r from-[#201b14] via-[#3d3324] to-[#201b14] border border-[#524430] shadow-2xl" />
    </div>
  );
};
