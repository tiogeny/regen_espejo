import React from 'react';
import { Camera, CameraOff, Sun, Maximize, MapPin } from 'lucide-react';
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
}

const PROBE_POINTS: ScanPoint[] = [
  { x: 47, y: 40, label: 'Pómulo derecho' },
  { x: 50, y: 31, label: 'Frente / Zona T' },
  { x: 50, y: 56, label: 'Barbilla' },
  { x: 53, y: 40, label: 'Pómulo izquierdo' },
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
}) => {
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 max-w-4xl w-[94vw] glass-panel-subtle rounded-2xl p-3 border border-[#dfc699]/25 shadow-2xl backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleWebcam}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border transition-all ${
              useWebcam
                ? 'bg-emerald-500/20 border-emerald-400/50 text-emerald-200'
                : 'bg-neutral-800/80 border-neutral-700 text-neutral-300 hover:text-white'
            }`}
          >
            {useWebcam ? <Camera className="w-3.5 h-3.5" /> : <CameraOff className="w-3.5 h-3.5" />}
            <span>{useWebcam ? 'Cámara Activa' : 'Modo Demo (Foto)'}</span>
          </button>

          <div className="flex items-center gap-1 bg-black/40 p-1 rounded-xl border border-neutral-800">
            {(['Mixta', 'Grasa', 'Seca', 'Sensible'] as SkinType[]).map((type) => (
              <button
                key={type}
                onClick={() => onSelectSkinType(type)}
                className={`px-2.5 py-1 rounded-lg text-[11px] transition-all ${
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

        <div className="flex items-center gap-1.5 text-neutral-300">
          <MapPin className="w-3.5 h-3.5 text-amber-300" />
          <span className="text-[11px] text-neutral-400">Punto:</span>
          <select
            value={currentZone}
            onChange={(e) => {
              const pt = PROBE_POINTS.find((p) => p.label === e.target.value) || PROBE_POINTS[0];
              onSelectProbeZone(pt);
            }}
            className="bg-black/50 border border-neutral-700 text-neutral-200 text-[11px] rounded-lg px-2 py-1 outline-none focus:border-amber-400"
          >
            {PROBE_POINTS.map((pt) => (
              <option key={pt.label} value={pt.label}>
                {pt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-black/40 p-1 rounded-xl border border-neutral-800">
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
              onClick={() => onChangeLightTone('cool')}
              className={`px-2 py-0.5 rounded-lg text-[10px] ${
                lightTone === 'cool' ? 'bg-sky-500/20 text-sky-200 border border-sky-400/50' : 'text-neutral-400'
              }`}
              title="Luz fría 6000K"
            >
              Frío
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
            <div className="hidden sm:flex items-center gap-1.5 pl-1">
              <Sun className="w-3.5 h-3.5 text-amber-300" />
              <input
                type="range"
                min="20"
                max="100"
                value={lightBrightness}
                onChange={(e) => onChangeBrightness(Number(e.target.value))}
                className="w-16 accent-amber-300 h-1"
                title="Intensidad de luz"
              />
            </div>
          )}

          <button
            onClick={onToggleFullscreen}
            className="p-1.5 rounded-xl bg-neutral-800/80 hover:bg-neutral-700 text-neutral-300 hover:text-white border border-neutral-700 transition-colors"
            title="Modo Espejo Pantalla Completa (F11)"
          >
            <Maximize className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
