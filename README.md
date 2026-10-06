# REGEN — Smart Mirror & Biocosmética Regenerativa (IA & Biodiversidad Peruana)

🌐 **Página Web en Vivo:** [https://tiogeny.github.io/regen_espejo/](https://tiogeny.github.io/regen_espejo/)

Prototipo de **Espejo Inteligente (Smart Mirror)** desarrollado para el ecosistema **Fab Lab Perú**, combinando **Visión Artificial / HUD Holográfico**, diagnóstico dérmico en tiempo real y **formulación biocosmética personalizada** a base de superingredientes nativos de la Amazonía y Andes peruanos.

---

## 🪞 Características Principales

1. **Interfaz Holográfica HUD (Smart Mirror):**
   - Marco de tocador circular con aro perimetral de luz LED regulable (Cálido 3000K, Neutro 4500K, Frío 6000K o Apagado) y control de brillo.
   - Reflejo en tiempo real mediante **cámara web** (con inversión en modo espejo `scaleX(-1)`) o **modo fotográfico demostrativo**.
   - Modo pantalla completa (**F11**) para convertir monitores y displays físicos en el Smart Mirror real.

2. **Diagnóstico Facial Dérmico con IA (Cero Tokens / 100% On-Device):**
   - Análisis óptico en cliente sobre la reflectancia especular (oleosidad) y varianza de microtextura (hidratación y poros).
   - Zoom microscópico 20x con visualización de los píxeles reales de tu piel.
   - Retícula táctil: haz clic en cualquier parte de tu rostro para analizar ese punto en vivo.
   - Clasificación de tipo de piel (*Mixta, Grasa, Seca, Sensible*).
   - Métricas continuas: **Hidratación (%)**, **Oleosidad (%)** y **pH cutáneo**.

3. **Motor de Bioformulación Automatizada ("Tu Bioproducto"):**
   - Gráfico SVG Donut interactivo con las proporciones activas de la fórmula.
   - Algoritmo que recalcula dinámicamente los porcentajes según las necesidades dérmicas.
   - Catálogo de bioingredientes peruanos:
     - **Aguaje (*Mauritia flexuosa*):** Rico en fitoestrógenos y betacaroteno para nutrición y elasticidad.
     - **Sacha Inchi (*Plukenetia volubilis*):** Omega 3, 6 y 9 para reparar el manto lipídico y regular el sebo.
     - **Camu Camu (*Myrciaria dubia*):** Máxima concentración de Vitamina C bioactiva y luminosidad.
     - **Huito (*Genipa americana*):** Astringente botánico suave y refinador de poros.
     - **Sangre de Grado (*Croton lechleri*):** Cicatrización y protección dérmica profunda.
     - **Copaiba (*Copaifera officinalis*):** Calma y equilibrio del microbioma.

4. **Integración con Biofabricación (Fab Lab Perú):**
   - Módulo simulador de dispensación y emulsificación en microfluídica.
   - Generación y exportación de fichas técnicas en formato `.json` para vincular a firmwares de dispensadores robóticos IoT (ESP32 / Arduino / Raspberry Pi).

---

## 🚀 Cómo ejecutarlo en tu computadora

### Requisitos:
- [Node.js](https://nodejs.org/) v18 o superior.
- Navegador moderno con soporte para WebRTC / Cámara Web (Chrome, Edge, Firefox, Brave).

### Pasos:

```bash
# 1. Instalar dependencias
npm install

# 2. Iniciar el servidor local
npm run dev
```

Abre tu navegador en:
```
http://localhost:5173
```
