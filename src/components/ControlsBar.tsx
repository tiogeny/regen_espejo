import React from 'react';
import { Camera, CameraOff, Sun, Maximize, Scan, Sparkles, MapPin } from 'lucide-react';
import type { SkinType, ScanPoint } from '../types';

interface ControlsBarProps {
  useWebcam: boolean;
  onToggleWebcam: () => void;
  selectedSkinType: SkinType;
  onSelectSkinType: (type: SkinType) => void;
  lightTone: 'warm' | 'neutral' | 'cool' | 'off';
  onChangeLightTone: (tone: 'warm' | 'neutral' | 'cool' | 'off') => void;
  lightBrightness: number;
  onChangeBrightness: (b: number) => void;
  onToggleFullscreen: () => void;
  onSelectProbeZone: (point: ScanPoint) => void;
  currentZone: string;
  onTriggerScan: () => void;
  isScanning: boolean;
}

const PROBE_POINTS: ScanPoint[] = [
  { x: 46.5, y: 41.5, label: 'Pómulo derecho' },
  { x: 50, y: 32, label: 'Frente / Zona T' },
  { x: 50, y: 56, label: 'Barbilla' },
  { x: 53.5, y: 41.5, label: 'Pómulo izquierdo' },
];

export const ControlsBar: React.FC<ControlsBarProps> = ({
  useWebcam,
  onToggleWebcam,
  selectedSkinType,
  onSelectSkinType,
  lightTone,
  onChangeLightTone,
  lightBrightness,
  onChangeBrightness,
  onToggleFullscreen,
  onSelectProbeZone,
  currentZone,
  onTriggerScan,
  isScanning,
}) => {
  return (
    <div className="fixed bottom-2 left-1/2 -translate-x-1/2 z-40 max-w-4xl w-[94vw] glass-panel-subtle rounded-2xl p-2.5 border border-[#dfc699]/30 shadow-2xl backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        {/* Botón principal: Escanear con IA */}
        <div className="flex items-center gap-2">
          <button
            onClick={onTriggerScan}
            disabled={isScanning}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl font-medium shadow-md transition-all ${
              isScanning
                ? 'bg-amber-500/40 text-amber-100 border border-amber-300 animate-pulse'
                : 'bg-gradient-to-r from-[#d9b77d] to-[#c79d5e] text-neutral-950 hover:brightness-110 active:scale-95'
            }`}
            title="Escanear piel y calibrar fórmula biológica"
          >
            {isScanning ? (
              <>
                <Scan className="w-4 h-4 animate-spin" />
                <span className="text-[11px] font-semibold">Analizando píxeles...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span className="text-[11px] font-semibold">Escanear Rostro (IA)</span>
              </>
            )}
          </button>

          {/* Botón Cámara */}
          <button
            onClick={onToggleWebcam}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border transition-all ${
              useWebcam
                ? 'bg-emerald-500/20 border-emerald-400/50 text-emerald-200'
                : 'bg-neutral-800/80 border-neutral-700 text-neutral-300 hover:text-white'
            }`}
            title="Encender o pausar la cámara web"
          >
            {useWebcam ? <Camera className="w-3.5 h-3.5" /> : <CameraOff className="w-3.5 h-3.5" />}
            <span className="text-[11px]">{useWebcam ? 'Cámara ON' : 'Cámara OFF'}</span>
          </button>
        </div>

        {/* Zona y Biotipos */}
        <div className="flex items-center gap-2">
          {/* Zona facial */}
          <div className="hidden sm:flex items-center gap-1 text-neutral-300 bg-black/40 px-2 py-1 rounded-xl border border-neutral-800">
            <MapPin className="w-3 h-3 text-amber-300" />
            <select
              value={currentZone}
              onChange={(e) => {
                const pt = PROBE_POINTS.find((p) => p.label === e.target.value) || PROBE_POINTS[0];
                onSelectProbeZone(pt);
              }}
              className="bg-transparent text-neutral-200 text-[10.5px] outline-none cursor-pointer"
            >
              {PROBE_POINTS.map((pt) => (
                <option key={pt.label} value={pt.label} className="bg-neutral-900 text-neutral-200">
                  {pt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Presets de piel */}
          <div className="flex items-center gap-0.5 bg-black/40 p-0.5 rounded-xl border border-neutral-800">
            {(['Mixta', 'Grasa', 'Seca', 'Sensible'] as SkinType[]).map((type) => (
              <button
                key={type}
                onClick={() => onSelectSkinType(type)}
                className={`px-2 py-1 rounded-lg text-[10.5px] transition-all ${
                  selectedSkinType === type
                    ? 'bg-[#d8be8a] text-neutral-950 font-semibold shadow-sm'
                    : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {/* Halo de Luz LED y Pantalla Completa */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-0.5 bg-black/40 p-0.5 rounded-xl border border-neutral-800">
            <button
              onClick={() => onChangeLightTone('warm')}
              className={`px-2 py-0.5 rounded-lg text-[10px] ${
                lightTone === 'warm' ? 'bg-amber-500/30 text-amber-200 border border-amber-400/50' : 'text-neutral-400'
              }`}
              title="Luz cálida 3000K"
            >
              Cálido
            </button>
            <button
              onClick={() => onChangeLightTone('neutral')}
              className={`px-2 py-0.5 rounded-lg text-[10px] ${
                lightTone === 'neutral' ? 'bg-neutral-200/20 text-white border border-white/40' : 'text-neutral-400'
              }`}
              title="Luz neutra 4500K"
            >
              Neutro
            </button>
            <button
              onClick={() => onChangeLightTone('off')}
              className={`px-2 py-0.5 rounded-lg text-[10px] ${
                lightTone === 'off' ? 'bg-red-500/20 text-red-200 border border-red-400/50' : 'text-neutral-400'
              }`}
              title="Apagar halo LED"
            >
              Off
            </button>
          </div>

          {lightTone !== 'off' && (
            <div className="hidden md:flex items-center gap-1 pl-1">
              <Sun className="w-3 h-3 text-amber-300" />
              <input
                type="range"
                min="30"
                max="100"
                value={lightBrightness}
                onChange={(e) => onChangeBrightness(Number(e.target.value))}
                className="w-14 accent-amber-300 h-1"
                title="Brillo LED"
              />
            </div>
          )}

          <button
            onClick={onToggleFullscreen}
            className="p-1.5 rounded-xl bg-neutral-800/80 hover:bg-neutral-700 text-neutral-300 hover:text-white border border-neutral-700 transition-colors"
            title="Pantalla Completa (F11)"
          >
            <Maximize className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
