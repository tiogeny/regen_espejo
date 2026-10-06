import { useState, useRef, useMemo, useEffect, useCallback } from 'react';
import { MirrorFrame } from './components/MirrorFrame';
import { ControlsBar } from './components/ControlsBar';
import { FabLabDispenserModal } from './components/FabLabDispenserModal';
import { useWebcam } from './hooks/useWebcam';
import { SKIN_PRESETS, INITIAL_PRODUCTS, calculateDynamicFormula } from './data/bioData';
import { analyzeSkinRegion } from './utils/skinAnalyzer';
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

  // Cámara activa por defecto para que inicie inmediatamente
  const [useCamera, setUseCamera] = useState(true);
  const [lightTone, setLightTone] = useState<'warm' | 'neutral' | 'cool' | 'off'>('warm');
  const [lightBrightness, setLightBrightness] = useState(85);
  const [dispenserProduct, setDispenserProduct] = useState<BioProduct | null>(null);

  // Estados de escaneo óptico por IA (0 tokens, client-side)
  const [isScanning, setIsScanning] = useState(false);
  const [macroImage, setMacroImage] = useState<string | undefined>(undefined);
  const [scanMessage, setScanMessage] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  useWebcam(videoRef, useCamera);

  // Recalcular el producto cuando cambian las métricas dérmicas
  const dynamicProducts = useMemo(() => {
    const list = [...INITIAL_PRODUCTS];
    list[0] = calculateDynamicFormula(metrics);
    return list;
  }, [metrics]);

  // Ejecutar análisis óptico en los píxeles de la cámara web
  const performOpticalScan = useCallback(() => {
    if (!videoRef.current || !useCamera) {
      setScanMessage('Modo simulación (sin cámara)');
      return;
    }

    setIsScanning(true);
    setScanMessage('Calibrando sensores ópticos...');

    setTimeout(() => {
      setScanMessage('Midiendo reflectancia sebácea y poros...');
    }, 800);

    setTimeout(() => {
      if (videoRef.current) {
        const result = analyzeSkinRegion(
          videoRef.current,
          activeScanPoint.x,
          activeScanPoint.y
        );

        if (result) {
          setMetrics(result.metrics);
          setSelectedSkinType(result.metrics.skinType);
          setMacroImage(result.macroImageDataUrl);
          setScanMessage(`¡Piel ${result.metrics.skinType} detectada! Fórmula ajustada.`);
        }
      }
      setIsScanning(false);
      setTimeout(() => setScanMessage(null), 3000);
    }, 1800);
  }, [activeScanPoint, useCamera]);

  // Si la cámara se enciende por primera vez, hacer un escaneo inicial suave
  useEffect(() => {
    if (useCamera && videoRef.current) {
      const timer = setTimeout(() => {
        performOpticalScan();
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [useCamera, performOpticalScan]);

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

  // Clic en cualquier punto del rostro dentro del espejo
  const handleMirrorClick = (xPercent: number, yPercent: number) => {
    const zoneName = yPercent < 36 ? 'Frente / Zona T' : yPercent > 52 ? 'Barbilla' : 'Pómulo';
    setActiveScanPoint({
      x: xPercent,
      y: yPercent,
      label: zoneName,
    });

    // Muestrear de inmediato los nuevos píxeles
    if (videoRef.current && useCamera) {
      const res = analyzeSkinRegion(videoRef.current, xPercent, yPercent);
      if (res) {
        setMacroImage(res.macroImageDataUrl);
      }
    }
  };

  const handleToggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  return (
    <div className="relative h-screen max-h-screen w-screen overflow-hidden bg-[#070908] text-neutral-100 flex flex-col justify-between items-center select-none">
      {/* Fondo con viñeta de iluminación ambiental */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(circle_at_50%_40%,rgba(217,183,125,0.06)_0%,rgba(0,0,0,0.95)_75%)]" />

      {/* Barra superior minimalista */}
      <header className="relative z-30 w-full px-6 pt-3 flex items-center justify-between text-xs pointer-events-none opacity-85">
        <div className="flex items-center gap-2 pointer-events-auto">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-mono text-[#d9b77d] tracking-wider text-[11px]">
            FAB LAB PERÚ · PROYECTO REGEN
          </span>
        </div>

        {/* Mensaje dinámico de escáner */}
        {scanMessage && (
          <div className="pointer-events-auto px-3 py-1 rounded-full bg-amber-400/20 border border-amber-300/40 text-amber-200 text-[11px] animate-pulse">
            ✨ {scanMessage}
          </div>
        )}

        <div className="hidden md:flex items-center gap-3 text-neutral-400 text-[11px] pointer-events-auto">
          <span>Smart Mirror IA</span>
          <span className="text-[#d9b77d]/60">·</span>
          <span>Bioingredientes Amazónicos</span>
        </div>
      </header>

      {/* Contenedor Central: Smart Mirror (auto-escalable y sin scroll) */}
      <main className="relative flex-1 w-full flex justify-center items-center overflow-hidden py-1">
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
          macroImage={macroImage}
          isScanning={isScanning}
          onMirrorClick={handleMirrorClick}
        />
      </main>

      {/* Barra de Controles Inferior */}
      <footer className="relative z-40 w-full flex justify-center pb-2">
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
          onTriggerScan={performOpticalScan}
          isScanning={isScanning}
        />
      </footer>

      {/* Modal de Dispensación Fab Lab */}
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
