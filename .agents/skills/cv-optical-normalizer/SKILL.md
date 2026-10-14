---
name: cv-optical-normalizer
description: Procedimientos clínicos y de visión artificial para normalización óptica de imágenes dermatológicas faciales mediante CLAHE en espacio LAB, filtrado bilateral edge-preserving y mitigación de reflejos de gafas.
---

# Skill: Normalización Óptica y Preprocesamiento Clínico

Esta skill guía la preparación de imágenes faciales para inferencia dermatológica en condiciones no controladas (webcams, iluminación variable de interiores).

## Procedimientos Clave

1. **Compensación de Iluminación con CLAHE en Espacio LAB**:
   - Convertir imagen RGB a LAB.
   - Aplicar CLAHE (ClipLimit=2.0, TileGridSize=(8,8)) estrictamente sobre el canal L (luminancia).
   - Reconectar canales A y B (crominancia intacta) y convertir de nuevo a RGB.
   - Beneficio: Normaliza sombras profundas bajo cejas, cuencas oculares y nariz sin alterar el tono biológico de la piel.

2. **Desacoplo de Grano con Filtrado Bilateral Edge-Preserving**:
   - `cv2.bilateralFilter(img, d=7, sigmaColor=45, sigmaSpace=45)`
   - Elimina ruido de alta frecuencia del sensor ISO de webcams sin alterar la geometría de ojos, nariz, labios ni contornos anatómicos.

3. **Detección de Accesorios / Gafas**:
   - Evaluar gradientes ópticos y profundidad z en los nodos peri-orbitales (MediaPipe nodos 33, 133, 362, 263).
