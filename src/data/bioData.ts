import type { BioProduct, SkinMetrics } from '../types';

export const SKIN_PRESETS: Record<string, SkinMetrics> = {
  mixta: {
    skinType: 'Mixta',
    hydration: 40,
    sebum: 60,
    ph: 5.5,
    pores: 52,
    elasticity: 68,
    zone: 'Pómulo derecho y mejilla',
  },
  grasa: {
    skinType: 'Grasa',
    hydration: 55,
    sebum: 82,
    ph: 6.2,
    pores: 75,
    elasticity: 60,
    zone: 'Zona T y mejillas',
  },
  seca: {
    skinType: 'Seca',
    hydration: 22,
    sebum: 20,
    ph: 4.8,
    pores: 28,
    elasticity: 45,
    zone: 'Pómulo y contorno',
  },
  sensible: {
    skinType: 'Sensible',
    hydration: 35,
    sebum: 42,
    ph: 5.0,
    pores: 38,
    elasticity: 50,
    zone: 'Mejillas y cuello',
  },
};

export const INITIAL_PRODUCTS: BioProduct[] = [
  {
    id: 'jabon-facial',
    title: 'TU BIÓPRODUCTO',
    name: 'Jabón Facial',
    tagline: 'Equilibra y purifica',
    phTarget: 5.5,
    category: 'Limpieza Botánica',
    description: 'Fórmula bioactiva en barra o gel frío diseñada para regular la producción sebácea de la zona T mientras nutre las áreas deshidratadas sin alterar el manto ácido.',
    ingredients: [
      {
        id: 'aguaje',
        name: 'Aguaje',
        scientificName: 'Mauritia flexuosa',
        percentage: 40,
        color: '#be4343',
        benefit: 'Rico en fitoestrógenos y pro-vitamina A. Regeneración celular y elasticidad.',
        origin: 'Aguajales de Loreto, Amazonía Peruana',
        activeNutrients: ['Betacaroteno', 'Ácido Oleico', 'Tocoferoles (Vit E)'],
      },
      {
        id: 'sacha-inchi',
        name: 'Sacha Inchi',
        scientificName: 'Plukenetia volubilis',
        percentage: 30,
        color: '#658d57',
        benefit: 'Equilibrio lipídico sin efecto graso. Restaura la barrera epidérmica.',
        origin: 'San Martín, Selva Alta del Perú',
        activeNutrients: ['Omega 3 (48%)', 'Omega 6 (36%)', 'Vitamina A'],
      },
      {
        id: 'camu-camu',
        name: 'Camu Camu',
        scientificName: 'Myrciaria dubia',
        percentage: 20,
        color: '#d4a86a',
        benefit: 'Mayor concentración de Vitamina C del planeta. Antioxidante y luminosidad.',
        origin: 'Riberas del Río Ucayali, Perú',
        activeNutrients: ['Vitamina C (30x naranja)', 'Flavonoides', 'Elagitaninos'],
      },
      {
        id: 'huito',
        name: 'Huito',
        scientificName: 'Genipa americana',
        percentage: 10,
        color: '#8b5a3c',
        benefit: 'Propiedades astringentes y purificantes suaves. Minimizador de poros.',
        origin: 'Bosque húmedo tropical, Madre de Dios',
        activeNutrients: ['Genipina', 'Taninos naturales', 'Bioflavonoides'],
      },
    ],
  },
  {
    id: 'serum-regenerador',
    title: 'TRATAMIENTO COMPLEMENTARIO',
    name: 'Sérum Regenerador',
    tagline: 'Restaura y reafirma',
    phTarget: 5.2,
    category: 'Nutrición Profunda',
    description: 'Suero de absorción rápida enriquecido con resina viva de Sangre de Grado para acelerar la regeneración dérmica y microtextura.',
    ingredients: [
      {
        id: 'sangre-grado',
        name: 'Sangre de Grado',
        scientificName: 'Croton lechleri',
        percentage: 35,
        color: '#9e2a2b',
        benefit: 'Cicatrizante natural y protector contra estrés oxidativo ambiental.',
        origin: 'Pucallpa, Selva Central',
        activeNutrients: ['Taspina', 'Proantocianidinas oligoméricas'],
      },
      {
        id: 'sacha-inchi',
        name: 'Sacha Inchi',
        scientificName: 'Plukenetia volubilis',
        percentage: 30,
        color: '#658d57',
        benefit: 'Hidratación no oclusiva con ácidos grasos esenciales.',
        origin: 'San Martín, Perú',
        activeNutrients: ['Omega 3', 'Omega 6'],
      },
      {
        id: 'aguaje',
        name: 'Aguaje',
        scientificName: 'Mauritia flexuosa',
        percentage: 25,
        color: '#be4343',
        benefit: 'Efecto antioxidante y fotoprotector biológico.',
        origin: 'Loreto, Perú',
        activeNutrients: ['Carotenoides', 'Vitamina E'],
      },
      {
        id: 'castana',
        name: 'Castaña Amazónica',
        scientificName: 'Bertholletia excelsa',
        percentage: 10,
        color: '#d4a86a',
        benefit: 'Aporte de Selenio biodisponible y suavidad sedosa.',
        origin: 'Madre de Dios, Perú',
        activeNutrients: ['Selenio orgánico', 'Fitoesteroles'],
      },
    ],
  },
  {
    id: 'bruma-tonificante',
    title: 'EQUILIBRIO DIARIO',
    name: 'Bruma Tonificante',
    tagline: 'Refresca e hidrata',
    phTarget: 5.6,
    category: 'Equilibrio de pH',
    description: 'Hidrolato botánico enriquecido con copaiba y camu camu para sellar la hidratación y calmar la inflamación reactiva.',
    ingredients: [
      {
        id: 'camu-camu',
        name: 'Camu Camu',
        scientificName: 'Myrciaria dubia',
        percentage: 45,
        color: '#d4a86a',
        benefit: 'Bio-shot de vitamina C que ilumina el cutis cansado.',
        origin: 'Ucayali, Perú',
        activeNutrients: ['Ácido ascórbico natural', 'Polifenoles'],
      },
      {
        id: 'copaiba',
        name: 'Bálsamo de Copaiba',
        scientificName: 'Copaifera officinalis',
        percentage: 25,
        color: '#4d7c58',
        benefit: 'Poderoso antiinflamatorio y equilibrador del microbioma.',
        origin: 'Cuenca del Marañón, Loreto',
        activeNutrients: ['Beta-cariofileno', 'Diterpenos'],
      },
      {
        id: 'aguaje',
        name: 'Aguaje',
        scientificName: 'Mauritia flexuosa',
        percentage: 20,
        color: '#be4343',
        benefit: 'Manto lipídico protector ligero.',
        origin: 'Loreto, Perú',
        activeNutrients: ['Betacaroteno'],
      },
      {
        id: 'huito',
        name: 'Huito',
        scientificName: 'Genipa americana',
        percentage: 10,
        color: '#8b5a3c',
        benefit: 'Regulación sutil de poros y tono cutáneo.',
        origin: 'Madre de Dios, Perú',
        activeNutrients: ['Genipósido', 'Iridoides'],
      },
    ],
  },
];

export function calculateDynamicFormula(metrics: SkinMetrics): BioProduct {
  const base = JSON.parse(JSON.stringify(INITIAL_PRODUCTS[0])) as BioProduct;

  let aguajePct = 40;
  let sachaPct = 30;
  let camuPct = 20;
  let huitoPct = 10;

  if (metrics.sebum > 65) {
    sachaPct += 10;
    huitoPct += 5;
    aguajePct -= 10;
    camuPct -= 5;
  } else if (metrics.hydration < 35) {
    aguajePct += 10;
    camuPct += 5;
    huitoPct -= 5;
    sachaPct -= 10;
  }

  const total = aguajePct + sachaPct + camuPct + huitoPct;
  base.ingredients[0].percentage = Math.round((aguajePct / total) * 100);
  base.ingredients[1].percentage = Math.round((sachaPct / total) * 100);
  base.ingredients[2].percentage = Math.round((camuPct / total) * 100);
  base.ingredients[3].percentage = 100 - (base.ingredients[0].percentage + base.ingredients[1].percentage + base.ingredients[2].percentage);

  base.phTarget = metrics.ph;
  return base;
}
