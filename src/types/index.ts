export type SkinType = 'Mixta' | 'Grasa' | 'Seca' | 'Normal' | 'Sensible';

export interface SkinMetrics {
  skinType: SkinType;
  hydration: number; // 0 - 100%
  sebum: number;     // 0 - 100% (Oleosidad)
  ph: number;        // ej. 5.5
  pores: number;     // 0 - 100%
  elasticity: number;// 0 - 100%
  zone: string;      // ej. 'Pómulo derecho', 'Zona T', 'Frente'
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
  title: string;
  name: string;
  tagline: string;
  phTarget: number;
  category: string;
  description: string;
  ingredients: BioIngredient[];
}

export interface ScanPoint {
  x: number; // percentage 0 - 100
  y: number; // percentage 0 - 100
  label: string;
  zoomImage?: string;
}
