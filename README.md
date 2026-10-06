# 🌿 REGEN · BioMirror — Estación Inteligente de Biocuidado & Biofabricación Personalizada

> **Smart Vanity & Real-Time On-Demand Biocosmetics Station**  
> Diagnóstico óptico por IA (0 tokens, 100% on-device) para **Rostro, Cabello, Sonrisa y Cuerpo** con formulación robótica basada en la **Biodiversidad Peruana (Amazonía y Andes)**.  
> Proyecto desarrollado para el ecosistema **Fab Lab Perú**.

🌐 **Aplicación Web en Vivo:** [https://tiogeny.github.io/regen_espejo/](https://tiogeny.github.io/regen_espejo/)

---

## 📸 Visión General del Sistema (Layout Panorámico 16:9)

```
┌─────────────────────────┬──────────────────────────┬─────────────────────────┐
│     PANEL IZQUIERDO     │      ESPEJO CENTRAL      │      PANEL DERECHO      │
│  (Biometría Anatómica)  │   (Smart Mirror Óptico)  │ (Estación Dispensadora) │
│                         │                          │                         │
│  🗺️ MAPA CORPORAL       │    🪞 REGEN SMART MIRROR │    🌿 FÓRMULA ACTIVA    │
│  • 👤 Piel Facial       │       CON CÁMARA WEB     │    • Donut Chart SVG %  │
│  • 💇 Cabello & Folículo│                          │    • Nutrientes nativos │
│  • 🦷 Sonrisa & Labios  │    [Retícula de escaneo] │    • Trazabilidad Perú  │
│  • ✋ Manos & Cuerpo    │    [Zoom microscópico 20x]│                         │
│                         │    [Halo LED regulable]  │    ⚙️ FAB LAB DISPENSER │
│  📊 DIAGNÓSTICO EN VIVO │                          │    • Tanques de reserva │
│  • Métricas específicas │                          │    • Dosificación JSON  │
│  • Bio-Clima y UV Perú  │                          │    • Bombeo peristáltico│
└─────────────────────────┴──────────────────────────┴─────────────────────────┘
```

---

## ✨ Características Principales

### 1. 🪞 Smart Mirror Central con Computer Vision (Cero Tokens, 100% On-Device)
- **Reflejo en tiempo real** mediante cámara web WebRTC con efecto espejo invertido.
- **Aro de luz LED perimetral regulable:** Modos Cálido (3000K), Neutro (4500K), Frío (6000K) y control de brillo.
- **Microscopía dérmica 20x:** El círculo de zoom proyecta la ampliación microscópica real de los píxeles capturados de tu piel/cabello.
- **Interacción directa táctil:** Al tocar cualquier parte de tu rostro en el espejo (frente, boca, barbilla, pómulos), la retícula viaja hacia allí y auto-selecciona la zona anatómica correspondiente.

### 2. 🗺️ Diagnóstico Multi-Zona Corporal
1. **👤 Piel Facial:** Analiza reflectancia sebácea, deshidratación y manto ácido -> Genera **Jabón Facial Botánico**.
2. **💇 Cabello & Cuero Cabelludo:** Mide porosidad de la cutícula y sebo en raíz -> Genera **Shampoo Sólido de Ungurahui**.
3. **🦷 Sonrisa & Labios:** Analiza escala de tono de esmalte y grietas labiales -> Genera **Pasta Dental de Arcilla Chaco & Menta Andina**.
4. **✋ Manos & Cuerpo:** Evalúa deshidratación por fricción y elasticidad -> Genera **Bálsamo Reparador de Murumuru & Castaña**.

### 3. 🇵🇪 Catálogo de Superingredientes de la Biodiversidad Peruana
- **Aguaje (*Mauritia flexuosa* - Loreto):** Fitoestrógenos y pro-vitamina A para nutrición dérmica profunda.
- **Sacha Inchi (*Plukenetia volubilis* - San Martín):** Omega 3, 6 y 9 para reparar la barrera lipídica sin oclusión.
- **Camu Camu (*Myrciaria dubia* - Ucayali):** Concentrado antioxidante con 30 veces más vitamina C que la naranja.
- **Ungurahui (*Oenocarpus bataua* - Loreto):** Reconstructor capilar amazónico tradicional.
- **Arcilla Chaco (*Caolín medicinal* - Puno):** Remineralización dental y purificación oral sin flúor tóxico.
- **Sangre de Grado (*Croton lechleri* - Selva Central):** Cicatrización acelerada de microheridas y grietas.
- **Cacao Blanco (*Theobroma cacao* - Piura):** Teobromina protectora del esmalte dental.
- **Menta Silvestre / Muña (*Minthostachys mollis* - Ayacucho):** Antiséptico bucal andino.

### 4. 🧪 Integración con Biofabricación (Fab Lab Perú)
- Monitoreo de niveles de tanques de extractos nativos.
- Simulación de calibración microfluídica y emulsificación en frío a 22°C.
- Exportación instantánea de órdenes de manufactura en formato `.json` para firmwares de microcontroladores (ESP32 / Arduino / Raspberry Pi).

---

## 🚀 Instalación y Uso Local

```bash
# 1. Clonar repositorio
git clone https://github.com/tiogeny/regen_espejo.git
cd regen_espejo

# 2. Instalar dependencias
npm install

# 3. Iniciar servidor local
npm run dev
```

Abre en tu navegador:
👉 **`http://localhost:5173/`**

- Presiona **F11** para entrar en modo espejo pantalla completa.
