import { useState, useRef, useMemo } from 'react';
import { MirrorFrame } from './components/MirrorFrame';
import { ControlsBar } from './components/ControlsBar';
import { FabLabDispenserModal } from './components/FabLabDispenserModal';
import { useWebcam } from './hooks/useWebcam';
import { SKIN_PRESETS, INITIAL_PRODUCTS, calculateDynamicFormula } from './data/bioData';
import type { SkinMetrics, BioProduct, SkinType, ScanPoint } from './types';

export function App() {
  const [selectedSkinType, setSelectedSkinType] = useState<SkinType>('Mixta');
  const [metrics, setMetrics] = useState<SkinMetrics>(SKIN_PRESETS.mixta);
  const [currentProductIndex, setCurrentProductIndex] = useState(0);
  const [activeScanPoint, setActiveScanPoint] = useState<ScanPoint>({
    x: 46.5,
    y: 41.5,
    label: 'Pómulo derecho',
  });

  const [useCamera, setUseCamera] = useState(false);
  const [lightTone, setLightTone] = useState<'warm' | 'neutral' | 'cool' | 'off'>('warm');
  const [lightBrightness, setLightBrightness] = useState(80);
  const [dispenserProduct, setDispenserProduct] = useState<BioProduct | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  useWebcam(videoRef, useCamera);

  // Recalcular el producto cuando cambian las métricas dérmicas
  const dynamicProducts = useMemo(() => {
    const list = [...INITIAL_PRODUCTS];
    list[0] = calculateDynamicFormula(metrics);
    return list;
  }, [metrics]);

  const handleSelectSkinType = (type: SkinType) => {
    setSelectedSkinType(type);
    const key = type.toLowerCase() as keyof typeof SKIN_PRESETS;
    if (SKIN_PRESETS[key]) {
      setMetrics(SKIN_PRESETS[key]);
    }
  };

  const handleUpdateMetric = (key: keyof SkinMetrics, value: number) => {
    setMetrics((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleToggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  return (
    <div className="relative min-h-screen bg-[#070908] text-neutral-100 flex flex-col justify-center items-center overflow-hidden selection:bg-[#d9b77d]/30">
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(circle_at_50%_35%,rgba(217,183,125,0.06)_0%,rgba(0,0,0,0.95)_75%)]" />

      <header className="fixed top-3 left-6 right-6 z-30 flex items-center justify-between text-xs pointer-events-none opacity-80 hover:opacity-100 transition-opacity">
        <div className="flex items-center gap-2 pointer-events-auto">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-mono text-[#d9b77d] tracking-wider text-[11px]">
            FAB LAB PERÚ · PROYECTO REGEN
          </span>
        </div>
        <div className="hidden md:flex items-center gap-4 text-neutral-400 text-[11px] pointer-events-auto">
          <span>Espejo Inteligente de Diagnóstico Dérmico</span>
          <span className="text-[#d9b77d]/60">|</span>
          <span>Bioingredientes Amazónicos</span>
        </div>
      </header>

      <main className="w-full flex justify-center items-center py-6">
        <MirrorFrame
          metrics={metrics}
          products={dynamicProducts}
          currentProductIndex={currentProductIndex}
          onSelectProduct={setCurrentProductIndex}
          onOpenDispenser={(prod) => setDispenserProduct(prod)}
          onUpdateMetric={handleUpdateMetric}
          videoRef={videoRef}
          useWebcam={useCamera}
          activeScanPoint={activeScanPoint}
          onSelectScanPoint={setActiveScanPoint}
          lightTone={lightTone}
          lightBrightness={lightBrightness}
        />
      </main>

      <ControlsBar
        useWebcam={useCamera}
        onToggleWebcam={() => setUseCamera(!useCamera)}
        selectedSkinType={selectedSkinType}
        onSelectSkinType={handleSelectSkinType}
        lightTone={lightTone}
        onChangeLightTone={setLightTone}
        lightBrightness={lightBrightness}
        onChangeBrightness={setLightBrightness}
        onToggleFullscreen={handleToggleFullscreen}
        onSelectProbeZone={(pt) => setActiveScanPoint(pt)}
        currentZone={activeScanPoint.label}
      />

      {dispenserProduct && (
        <FabLabDispenserModal
          product={dispenserProduct}
          metrics={metrics}
          onClose={() => setDispenserProduct(null)}
        />
      )}
    </div>
  );
}

export default App;
