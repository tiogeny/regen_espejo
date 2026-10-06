import React from 'react';
import { Camera, CameraOff, Sun, Maximize, Scan, Sparkles } from 'lucide-react';

interface ControlsBarProps {
  useWebcam: boolean;
  onToggleWebcam: () => void;
  lightTone: 'warm' | 'neutral' | 'cool' | 'off';
  onChangeLightTone: (tone: 'warm' | 'neutral' | 'cool' | 'off') => void;
  lightBrightness: number;
  onChangeBrightness: (b: number) => void;
  onToggleFullscreen: () => void;
  onTriggerScan: () => void;
  isScanning: boolean;
}

export const ControlsBar: React.FC<ControlsBarProps> = ({
  useWebcam,
  onToggleWebcam,
  lightTone,
  onChangeLightTone,
  lightBrightness,
  onChangeBrightness,
  onToggleFullscreen,
  onTriggerScan,
  isScanning,
}) => {
  return (
    <div className="glass-panel-subtle rounded-2xl px-4 py-2 border border-[#dfc699]/30 shadow-2xl backdrop-blur-xl">
      <div className="flex items-center gap-3 text-xs">
        {/* Botón principal: Escanear con IA */}
        <button
          onClick={onTriggerScan}
          disabled={isScanning}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl font-medium shadow-md transition-all ${
            isScanning
              ? 'bg-amber-500/40 text-amber-100 border border-amber-300 animate-pulse'
              : 'bg-gradient-to-r from-[#d9b77d] to-[#c79d5e] text-neutral-950 hover:brightness-110 active:scale-95'
          }`}
          title="Escanear zona corporal y calibrar fórmula"
        >
          {isScanning ? (
            <>
              <Scan className="w-4 h-4 animate-spin" />
              <span className="text-[11px] font-semibold">Analizando píxeles...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span className="text-[11px] font-semibold">Escanear Zona con IA</span>
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
          title="Encender o apagar cámara web"
        >
          {useWebcam ? <Camera className="w-3.5 h-3.5" /> : <CameraOff className="w-3.5 h-3.5" />}
          <span className="text-[11px]">{useWebcam ? 'Cámara ON' : 'Cámara OFF'}</span>
        </button>

        {/* Separador */}
        <div className="w-[1px] h-4 bg-neutral-700/60 hidden sm:block" />

        {/* Halo de Luz LED */}
        <div className="flex items-center gap-1 bg-black/40 p-0.5 rounded-xl border border-neutral-800">
          <button
            onClick={() => onChangeLightTone('warm')}
            className={`px-2 py-0.5 rounded-lg text-[10px] ${
              lightTone === 'warm' ? 'bg-amber-500/30 text-amber-200 border border-amber-400/50' : 'text-neutral-400'
            }`}
          >
            Cálido
          </button>
          <button
            onClick={() => onChangeLightTone('neutral')}
            className={`px-2 py-0.5 rounded-lg text-[10px] ${
              lightTone === 'neutral' ? 'bg-neutral-200/20 text-white border border-white/40' : 'text-neutral-400'
            }`}
          >
            Neutro
          </button>
          <button
            onClick={() => onChangeLightTone('cool')}
            className={`px-2 py-0.5 rounded-lg text-[10px] ${
              lightTone === 'cool' ? 'bg-sky-500/20 text-sky-200 border border-sky-400/50' : 'text-neutral-400'
            }`}
          >
            Frío
          </button>
          <button
            onClick={() => onChangeLightTone('off')}
            className={`px-2 py-0.5 rounded-lg text-[10px] ${
              lightTone === 'off' ? 'bg-red-500/20 text-red-200 border border-red-400/50' : 'text-neutral-400'
            }`}
          >
            Off
          </button>
        </div>

        {/* Brillo LED */}
        {lightTone !== 'off' && (
          <div className="hidden md:flex items-center gap-1 pl-0.5">
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

        {/* Pantalla Completa */}
        <button
          onClick={onToggleFullscreen}
          className="p-1.5 rounded-xl bg-neutral-800/80 hover:bg-neutral-700 text-neutral-300 hover:text-white border border-neutral-700 transition-colors ml-auto"
          title="Pantalla Completa (F11)"
        >
          <Maximize className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
