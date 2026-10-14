---
name: derma-segmentation-fitzpatrick
description: Procedimientos de segmentación de manchas cutáneas con U-Net Nano y clasificación espectral de fototipos de piel Fitzpatrick (I-VI) mediante el ángulo tipológico individual (ITA).
---

# Skill: Segmentación Dermatológica y Fototipos Fitzpatrick

Esta skill define la calibración espectral de piel y cuantificación de hiperpigmentación adaptada al fototipo cutáneo del paciente.

## Procedimientos Clave

1. **Cálculo del Ángulo Tipológico Individual (ITA)**:
   - Extraer parche cutáneo en zona malar/mandíbula libre de vello y maquillaje.
   - Convertir parche RGB a CIELAB ($L^*, a^*, b^*$).
   - Calcular:
     $$ITA = \arctan\left(\frac{L^* - 50}{b^*}\right) \times \frac{180}{\pi}$$
   - Mapeo a Escala Fitzpatrick:
     - Muy Clara ($ITA > 55°$): Fototipo I (Muy claro)
     - Clara ($41° < ITA \le 55°$): Fototipo II
     - Intermedia ($28° < ITA \le 41°$): Fototipo III
     - Bronceada / Morena ($10° < ITA \le 28°$): Fototipo IV
     - Oscura ($-30° < ITA \le 10°$): Fototipo V
     - Muy Oscura ($ITA \le -30°$): Fototipo VI

2. **Calibración Dinámica de Umbrales de Segmentación U-Net Nano**:
   - Para fototipos claros (I-II), umbralizar diferencias de melanina en $\Delta \ge 0.14$.
   - Para fototipos intermedios/oscuros (III-VI), ajustar umbral dinámico para evitar falsos positivos con pigmentación fisiológica basal.
