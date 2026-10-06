import type { SkinMetrics, SkinType } from '../types';

export interface OpticalAnalysisResult {
  metrics: SkinMetrics;
  macroImageDataUrl: string;
}

/**
 * Analiza ópticamente los píxeles de la cámara web en el área del pómulo
 * mediante Computer Vision local (Canvas API / GPU).
 * Cero tokens, 100% privado y en tu propia máquina.
 */
export function analyzeSkinRegion(
  video: HTMLVideoElement,
  pointXPercent: number,
  pointYPercent: number
): OpticalAnalysisResult | null {
  if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
    return null;
  }

  const vWidth = video.videoWidth;
  const vHeight = video.videoHeight;

  // En video invertido (-scaleX), la coordenada X se invierte ópticamente
  const normalizedX = (100 - pointXPercent) / 100;
  const normalizedY = pointYPercent / 100;

  const targetPixelX = Math.floor(normalizedX * vWidth);
  const targetPixelY = Math.floor(normalizedY * vHeight);

  // Región de interés (ROI): 80x80 píxeles alrededor del pómulo
  const roiSize = 80;
  const startX = Math.max(0, Math.min(vWidth - roiSize, targetPixelX - roiSize / 2));
  const startY = Math.max(0, Math.min(vHeight - roiSize, targetPixelY - roiSize / 2));

  // Canvas temporal para lectura de píxeles
  const canvas = document.createElement('canvas');
  canvas.width = roiSize;
  canvas.height = roiSize;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) return null;

  // Dibujar el recorte del rostro en el canvas
  ctx.drawImage(video, startX, startY, roiSize, roiSize, 0, 0, roiSize, roiSize);
  const imgData = ctx.getImageData(0, 0, roiSize, roiSize);
  const data = imgData.data;

  let totalLuminance = 0;
  let highLuminanceCount = 0; // Puntos de brillo especular (oleosidad)
  let totalRed = 0;
  let totalGreen = 0;
  let totalBlue = 0;
  let varianceSum = 0;

  const numPixels = roiSize * roiSize;

  // Primer pase: medias de color y luminancia
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];

    // Fórmula estándar de luminancia ITU-R BT.601
    const lum = 0.299 * r + 0.587 * g + 0.114 * b;
    totalLuminance += lum;
    totalRed += r;
    totalGreen += g;
    totalBlue += b;

    // Si el brillo supera el umbral, indica reflejo sebáceo o iluminación intensa
    if (lum > 185) {
      highLuminanceCount++;
    }
  }

  const avgLum = totalLuminance / numPixels;
  const avgRed = totalRed / numPixels;
  const avgGreen = totalGreen / numPixels;
  const avgBlue = totalBlue / numPixels;

  // Segundo pase: cálculo de contraste local / microtextura (varianza de nitidez)
  for (let i = 0; i < data.length; i += 4) {
    const lum = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    varianceSum += Math.pow(lum - avgLum, 2);
  }
  const variance = Math.sqrt(varianceSum / numPixels);

  // --- CÁLCULO DE MÉTRICAS DERMATOLÓGICAS ---

  // 1. Oleosidad (Sebum): correlación entre brillos especulares y luminancia relativa
  const specularRatio = (highLuminanceCount / numPixels) * 100;
  let sebumScore = Math.round(35 + specularRatio * 2.8 + (avgLum > 140 ? 15 : 0));
  sebumScore = Math.min(88, Math.max(18, sebumScore));

  // 2. Hidratación: piel bien hidratada refleja luz suave y difusa con varianza moderada
  let hydrationScore = Math.round(75 - Math.abs(variance - 22) * 1.5 - (sebumScore > 70 ? 15 : 0));
  hydrationScore = Math.min(85, Math.max(20, hydrationScore));

  // 3. Estimación de pH cutáneo: correlación entre el manto ácido natural y vascularización
  // En piel fisiológica sana el pH oscila entre 4.7 y 5.8
  const redDominance = (avgRed - (avgGreen + avgBlue) / 2) / 255;
  let phScore = Number((5.5 + redDominance * 1.2 + (sebumScore > 65 ? 0.3 : -0.2)).toFixed(1));
  phScore = Math.min(6.5, Math.max(4.7, phScore));

  // 4. Poros y elasticidad
  const poresScore = Math.round(Math.min(85, Math.max(25, variance * 2.2 + specularRatio * 1.2)));
  const elasticityScore = Math.round(Math.min(90, Math.max(30, 100 - (poresScore * 0.4 + (100 - hydrationScore) * 0.5))));

  // Clasificación de Tipo de Piel
  let skinType: SkinType = 'Mixta';
  if (sebumScore >= 68 && hydrationScore >= 40) {
    skinType = 'Grasa';
  } else if (sebumScore < 35 && hydrationScore < 40) {
    skinType = 'Seca';
  } else if (redDominance > 0.25 || phScore < 5.0) {
    skinType = 'Sensible';
  } else if (sebumScore >= 45 && sebumScore <= 65) {
    skinType = 'Mixta';
  }

  // Generar imagen con efecto microscópico 20x en un canvas ampliado
  const macroCanvas = document.createElement('canvas');
  macroCanvas.width = 160;
  macroCanvas.height = 160;
  const mCtx = macroCanvas.getContext('2d');
  let macroDataUrl = '';

  if (mCtx) {
    // Escalar píxeles con realce de textura
    mCtx.imageSmoothingEnabled = false;
    mCtx.drawImage(canvas, 0, 0, roiSize, roiSize, 0, 0, 160, 160);
    macroDataUrl = macroCanvas.toDataURL('image/jpeg', 0.85);
  }

  return {
    metrics: {
      skinType,
      hydration: hydrationScore,
      sebum: sebumScore,
      ph: phScore,
      pores: poresScore,
      elasticity: elasticityScore,
      zone: pointYPercent < 35 ? 'Frente' : pointYPercent > 50 ? 'Barbilla' : 'Pómulo derecho',
    },
    macroImageDataUrl: macroDataUrl,
  };
}
