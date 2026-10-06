export type BodyZone = 'rostro' | 'cabello' | 'sonrisa' | 'cuerpo';
export type SkinType = 'Mixta' | 'Grasa' | 'Seca' | 'Normal' | 'Sensible';

export interface SkinMetrics {
  skinType: SkinType;
  hydration: number; // 0 - 100%
  sebum: number;     // 0 - 100%
  ph: number;        // ej. 5.5
  pores: number;     // 0 - 100%
  elasticity: number;// 0 - 100%
  zone: string;
}

export interface MetricItem {
  id: string;
  label: string;
  value: number; // 0 - 100
  displayValue: string;
  color: string;
  iconType: 'droplet' | 'wind' | 'sparkles' | 'shield' | 'flame';
}

export interface ZoneAnalysis {
  zone: BodyZone;
  title: string;
  subtitle: string;
  typeLabel: string;
  typeName: string;
  metrics: MetricItem[];
  defaultScanPoint: ScanPoint;
}

export interface BioIngredient {
  id: string;
  name: string;
  scientificName: string;
  percentage: number;
  color: string;
  benefit: string;
  origin: string;
  activeNutrients: string[];
}

export interface BioProduct {
  id: string;
  zone: BodyZone;
  title: string;
  name: string;
  tagline: string;
  phTarget: number;
  category: string;
  description: string;
  ingredients: BioIngredient[];
}

export interface ScanPoint {
  x: number;
  y: number;
  label: string;
  zoomImage?: string;
}

export interface TankLevel {
  id: string;
  name: string;
  origin: string;
  level: number;
  color: string;
}
