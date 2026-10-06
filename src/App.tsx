import { useState, useRef, useEffect, useCallback } from 'react';
import { MirrorFrame } from './components/MirrorFrame';
import { BodyZoneSelector } from './components/BodyZoneSelector';
import { FabLabDispenserPanel } from './components/FabLabDispenserPanel';
import { ControlsBar } from './components/ControlsBar';
import { FabLabDispenserModal } from './components/FabLabDispenserModal';
import { useWebcam } from './hooks/useWebcam';
import { ZONE_ANALYSIS_DATA, ZONE_PRODUCTS, FAB_LAB_TANKS } from './data/bioData';
import { analyzeSkinRegion } from './utils/skinAnalyzer';
import type { BodyZone, ScanPoint, BioProduct } from './types';

export function App() {
  const [currentZone, setCurrentZone] = useState<BodyZone>('rostro');
  const [zoneData, setZoneData] = useState(ZONE_ANALYSIS_DATA.rostro);
  const [currentProduct, setCurrentProduct] = useState<BioProduct>(ZONE_PRODUCTS.rostro);
  const [activeScanPoint, setActiveScanPoint] = useState<ScanPoint>(ZONE_ANALYSIS_DATA.rostro.defaultScanPoint);

  const [useCamera, setUseCamera] = useState(true);
  const [lightTone, setLightTone] = useState<'warm' | 'neutral' | 'cool' | 'off'>('warm');
  const [lightBrightness, setLightBrightness] = useState(85);
  const [dispenserModalProduct, setDispenserModalProduct] = useState<BioProduct | null>(null);

  const [isScanning, setIsScanning] = useState(false);
  const [macroImage, setMacroImage] = useState<string | undefined>(undefined);
  const [scanMessage, setScanMessage] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  useWebcam(videoRef, useCamera);

  // Cambiar de zona anatómica (Rostro, Cabello, Sonrisa, Cuerpo)
  const handleSelectZone = useCallback((zone: BodyZone) => {
    setCurrentZone(zone);
    const data = ZONE_ANALYSIS_DATA[zone];
    setZoneData(data);
    setCurrentProduct(ZONE_PRODUCTS[zone]);
    setActiveScanPoint(data.defaultScanPoint);

    // Muestreo óptico inmediato si la cámara está activa
    if (videoRef.current && useCamera) {
      const res = analyzeSkinRegion(videoRef.current, data.defaultScanPoint.x, data.defaultScanPoint.y);
      if (res) {
        setMacroImage(res.macroImageDataUrl);
      }
    }
  }, [useCamera]);

  // Ejecutar escaneo óptico por IA
  const performOpticalScan = useCallback(() => {
    if (!videoRef.current || !useCamera) {
      setScanMessage('Modo demostración (sin cámara)');
      return;
    }

    setIsScanning(true);
    setScanMessage(`Escaneando ${zoneData.title}...`);

    setTimeout(() => {
      setScanMessage('Analizando textura, reflectancia y lípidos...');
    }, 800);

    setTimeout(() => {
      if (videoRef.current) {
        const result = analyzeSkinRegion(
          videoRef.current,
          activeScanPoint.x,
          activeScanPoint.y
        );

        if (result) {
          setMacroImage(result.macroImageDataUrl);

          // Actualizar métricas dinámicas de la zona según el escaneo real
          setZoneData((prev) => {
            const next = { ...prev };
            if (currentZone === 'rostro') {
              next.metrics[0].value = result.metrics.hydration;
              next.metrics[0].displayValue = `${result.metrics.hydration}%`;
              next.metrics[1].value = result.metrics.sebum;
              next.metrics[1].displayValue = `${result.metrics.sebum}%`;
              next.metrics[2].displayValue = result.metrics.ph.toFixed(1);
            } else if (currentZone === 'cabello') {
              next.metrics[1].value = result.metrics.sebum;
              next.metrics[1].displayValue = `${result.metrics.sebum}%`;
            } else if (currentZone === 'sonrisa') {
              next.metrics[1].value = result.metrics.hydration;
              next.metrics[1].displayValue = `${result.metrics.hydration}%`;
            } else if (currentZone === 'cuerpo') {
              next.metrics[0].value = result.metrics.elasticity;
              next.metrics[0].displayValue = `${result.metrics.elasticity}%`;
            }
            return next;
          });

          setScanMessage(`¡${zoneData.title} analizado con éxito! Fórmula bioactiva adaptada.`);
        }
      }
      setIsScanning(false);
      setTimeout(() => setScanMessage(null), 3000);
    }, 1800);
  }, [activeScanPoint, currentZone, useCamera, zoneData.title]);

  // Escaneo inicial suave al cargar la cámara
  useEffect(() => {
    if (useCamera && videoRef.current) {
      const timer = setTimeout(() => {
        performOpticalScan();
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [useCamera, performOpticalScan]);

  // Clic en cualquier punto del espejo
  const handleMirrorClick = (xPercent: number, yPercent: number) => {
    // Si hace clic en la parte superior del espejo (y < 30) -> auto-selecciona Cabello
    if (yPercent < 30 && currentZone !== 'cabello') {
      handleSelectZone('cabello');
      return;
    }
    // Si hace clic en la boca (y entre 48 y 58 y centro) -> auto-selecciona Sonrisa
    if (yPercent >= 48 && yPercent <= 58 && xPercent >= 42 && xPercent <= 58 && currentZone !== 'sonrisa') {
      handleSelectZone('sonrisa');
      return;
    }
    // Si hace clic abajo (y > 60) -> auto-selecciona Cuerpo
    if (yPercent > 62 && currentZone !== 'cuerpo') {
      handleSelectZone('cuerpo');
      return;
    }

    setActiveScanPoint({
      x: xPercent,
      y: yPercent,
      label: `Punto (${Math.round(xPercent)}%, ${Math.round(yPercent)}%)`,
    });

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
    <div className="relative h-screen max-h-screen w-screen overflow-hidden bg-[#070908] text-neutral-100 flex flex-col justify-between items-center select-none p-3">
      {/* Fondo ambiental */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(circle_at_50%_40%,rgba(217,183,125,0.06)_0%,rgba(0,0,0,0.95)_75%)]" />

      {/* Barra superior */}
      <header className="relative z-30 w-full px-4 flex items-center justify-between text-xs pointer-events-none opacity-85">
        <div className="flex items-center gap-2 pointer-events-auto">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-mono text-[#d9b77d] tracking-wider text-[11px] font-semibold">
            REGEN · BIOMIRROR · FAB LAB PERÚ
          </span>
        </div>

        {scanMessage && (
          <div className="pointer-events-auto px-3.5 py-1 rounded-full bg-amber-400/20 border border-amber-300/40 text-amber-200 text-[11px] animate-pulse">
            ✨ {scanMessage}
          </div>
        )}

        <div className="hidden md:flex items-center gap-3 text-neutral-400 text-[11px] pointer-events-auto">
          <span>Smart Vanity & Biocuidado Integral</span>
          <span className="text-[#d9b77d]/60">·</span>
          <span>Biodiversidad Peruana</span>
        </div>
      </header>

      {/* Distribución Horizontal Panorámica (16:9) */}
      <main className="relative z-20 flex-1 w-full max-w-[1550px] flex items-center justify-between gap-4 px-2 overflow-hidden">
        {/* Columna Izquierda: Mapa Anatómico & Diagnóstico */}
        <div className="hidden lg:flex flex-shrink-0">
          <BodyZoneSelector
            currentZone={currentZone}
            onSelectZone={handleSelectZone}
            zoneData={zoneData}
          />
        </div>

        {/* Columna Central: Smart Mirror */}
        <div className="flex-1 flex justify-center items-center">
          <MirrorFrame
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
        </div>

        {/* Columna Derecha: Bioproducto & Estación Fab Lab */}
        <div className="hidden lg:flex flex-shrink-0">
          <FabLabDispenserPanel
            product={currentProduct}
            tanks={FAB_LAB_TANKS}
            onOpenDispenser={(prod) => setDispenserModalProduct(prod)}
          />
        </div>
      </main>

      {/* Barra de Controles Inferior */}
      <footer className="relative z-40 w-full flex justify-center pb-1">
        <ControlsBar
          useWebcam={useCamera}
          onToggleWebcam={() => setUseCamera(!useCamera)}
          lightTone={lightTone}
          onChangeLightTone={setLightTone}
          lightBrightness={lightBrightness}
          onChangeBrightness={setLightBrightness}
          onToggleFullscreen={handleToggleFullscreen}
          onTriggerScan={performOpticalScan}
          isScanning={isScanning}
        />
      </footer>

      {/* Modal de Dispensación en Fab Lab */}
      {dispenserModalProduct && (
        <FabLabDispenserModal
          product={dispenserModalProduct}
          metrics={{
            skinType: 'Mixta',
            hydration: 40,
            sebum: 60,
            ph: 5.5,
            pores: 50,
            elasticity: 60,
            zone: zoneData.title,
          }}
          onClose={() => setDispenserModalProduct(null)}
        />
      )}
    </div>
  );
}

export default App;
