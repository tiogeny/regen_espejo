import React, { useState, useEffect } from 'react';
import { X, CheckCircle2, Download, Cpu, RefreshCw } from 'lucide-react';
import confetti from 'canvas-confetti';
import type { BioProduct, SkinMetrics } from '../types';

interface FabLabDispenserModalProps {
  product: BioProduct | null;
  metrics: SkinMetrics;
  onClose: () => void;
}

export const FabLabDispenserModal: React.FC<FabLabDispenserModalProps> = ({
  product,
  metrics,
  onClose,
}) => {
  if (!product) return null;

  const [dispenseProgress, setDispenseProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('Iniciando calibración de bombas peristálticas...');
  const [isCompleted, setIsCompleted] = useState(false);

  useEffect(() => {
    const steps = [
      'Calibrando válvulas microfluídicas...',
      'Dosificando base botánica neutra (pH 5.5)...',
      `Inyectando extracto de ${product.ingredients[0].name} (${product.ingredients[0].percentage}%)...`,
      `Inyectando activo de ${product.ingredients[1].name} (${product.ingredients[1].percentage}%)...`,
      `Inyectando extracto de ${product.ingredients[2].name} (${product.ingredients[2].percentage}%)...`,
      `Adicionando estabilizador de ${product.ingredients[3].name} (${product.ingredients[3].percentage}%)...`,
      'Emulsionando por microcavitación en frío (22°C)...',
      'Verificando pH dermatológico en línea (5.5)...',
      '¡Bioproducto personalizado listo para envasado!',
    ];

    let current = 0;
    const interval = setInterval(() => {
      current++;
      if (current < steps.length) {
        setCurrentStep(steps[current]);
        setDispenseProgress(Math.round((current / (steps.length - 1)) * 100));
      } else {
        clearInterval(interval);
        setIsCompleted(true);
        confetti({
          particleCount: 80,
          spread: 60,
          origin: { y: 0.6 },
          colors: ['#e7cca2', '#658d57', '#be4343', '#d4a86a'],
        });
      }
    }, 700);

    return () => clearInterval(interval);
  }, [product]);

  const handleDownloadRecipe = () => {
    const recipeData = {
      project: 'REGEN — Fab Lab Perú Biocosmética',
      timestamp: new Date().toISOString(),
      patientMetrics: metrics,
      bioproduct: {
        name: product.name,
        category: product.category,
        batchId: `BATCH-REGEN-${Date.now().toString().slice(-6)}`,
        targetVolumeMl: 100,
        ingredients: product.ingredients.map((ing) => ({
          name: ing.name,
          scientificName: ing.scientificName,
          percentage: ing.percentage,
          volumeMl: (ing.percentage * 1.0).toFixed(1),
          origin: ing.origin,
        })),
      },
    };

    const blob = new Blob([JSON.stringify(recipeData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `formula-${product.id}-regen.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-md flex items-center justify-center p-4">
      <div className="relative w-full max-w-xl glass-panel rounded-3xl p-6 border border-[#dfc699]/40 shadow-2xl animate-fadeIn">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-neutral-400 hover:text-white p-1 rounded-full hover:bg-white/10 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-2xl bg-[#d8be8a]/20 border border-[#d8be8a]/40 flex items-center justify-center text-[#edd3aa]">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] tracking-[0.2em] text-[#d8be8a] uppercase font-mono">
              ESTACIÓN DE BIOFABRICACIÓN · FAB LAB PERÚ
            </span>
            <h3 className="text-lg font-light text-neutral-100">
              Formulando {product.name} a Medida
            </h3>
          </div>
        </div>

        <div className="mb-6 bg-black/40 p-4 rounded-2xl border border-neutral-700/40">
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-neutral-300 flex items-center gap-2">
              {!isCompleted ? (
                <RefreshCw className="w-3.5 h-3.5 text-amber-300 animate-spin" />
              ) : (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              )}
              {currentStep}
            </span>
            <span className="font-mono text-amber-200 font-bold">{dispenseProgress}%</span>
          </div>

          <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-[#be4343] via-[#d4a86a] to-[#658d57] transition-all duration-500 rounded-full"
              style={{ width: `${dispenseProgress}%` }}
            />
          </div>
        </div>

        <div className="space-y-2 mb-6">
          <span className="text-xs uppercase text-neutral-400 font-mono tracking-wider">
            Dosificación por alícuota (Total: 100 mL):
          </span>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {product.ingredients.map((ing) => (
              <div
                key={ing.id}
                className="p-2.5 rounded-xl bg-neutral-900/60 border border-neutral-800 flex items-center justify-between"
              >
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: ing.color }} />
                    <span className="font-medium text-neutral-200">{ing.name}</span>
                  </div>
                  <span className="text-[10px] text-neutral-400 block pl-3.5">{ing.origin.split(',')[0]}</span>
                </div>
                <div className="text-right">
                  <span className="font-mono text-amber-200 font-semibold">{ing.percentage} mL</span>
                  <span className="text-[10px] text-neutral-400 block">({ing.percentage}%)</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-neutral-800">
          <div className="text-xs text-neutral-400">
            Diagnóstico vinculado: <strong className="text-neutral-200">{metrics.skinType}</strong> (Hidr: {metrics.hydration}%, Oleo: {metrics.sebum}%)
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleDownloadRecipe}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs bg-neutral-800 hover:bg-neutral-700 text-neutral-200 border border-neutral-700 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Exportar Ficha JSON</span>
            </button>

            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs bg-[#d9b77d] hover:bg-[#e7ca94] text-neutral-950 font-semibold transition-colors shadow-md"
            >
              {isCompleted ? 'Finalizar' : 'Cerrar'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
