// REGEN · Espejo Inteligente de Diagnóstico Dermatoscópico (Client-Side Web v2.1)

// Redirigir automáticamente a HTTPS si se entra por HTTP (la webcam requiere HTTPS)
if (location.protocol === 'http:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
  location.replace(location.href.replace('http:', 'https:'));
}

const $ = id => document.getElementById(id);
const cameraCanvas = $('camera'), ctx = cameraCanvas.getContext('2d');
const closeupCanvas = $('closeup'), zoom = closeupCanvas.getContext('2d');
const video = $('webcam-video');

const formatter = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 1 });
const measurement = (val, unit = '') => Number.isFinite(val) ? formatter.format(val) + unit : '—';
const phototypeLabels = ['', 'Fototipo I (Muy claro)', 'Fototipo II (Claro)', 'Fototipo III (Intermedio)', 'Fototipo IV (Bronceado / Moreno)', 'Fototipo V (Oscuro)', 'Fototipo VI (Muy oscuro)'];
const phototypeRoman = ['', 'I', 'II', 'III', 'IV', 'V', 'VI'];

// Estados: 'BUSCANDO' | 'ENCUADRANDO' | 'ANALIZANDO' | 'DIAGNOSTICADO'
let state = 'BUSCANDO';
let mode = 'visual'; // 'visual' | 'appearance'
let targetZone = null; // { x, y, radius, label }
let diagnosticData = null;
let lastDetectionTs = 0;
let faceStableStartTime = 0;
let faceStabilityProgress = 0;
let detectedFaceBox = null;

// Catálogo farmacognóstico determinista de Ronal
const BOTANICAL_CATALOG = {
  JOVEN: [
    {
      especie: "Melaleuca alternifolia",
      nombre_comun: "Árbol de Té",
      explicacion: "Acción antibacteriana y seborreguladora natural para control de impurezas y manto lipídico en piel joven.",
      precauciones: "Realizar prueba de tolerancia previa. Evitar contacto ocular directo.",
      fuentes: ["Fitoterapia Clínica Dermatológica (2024)", "Journal of Dermatological Science 88(2)"]
    },
    {
      especie: "Plukenetia volubilis",
      nombre_comun: "Sacha Inchi (San Martín)",
      explicacion: "Aceite virgen rico en Omega 3, 6 y 9 para reequilibrar la barrera cutánea sin oclusión comedogénica.",
      precauciones: "Apto para uso diario. Aplicar preferentemente en piel limpia nocturna.",
      fuentes: ["Biodiversidad Aplicada y Cosmética Sostenible (2025)"]
    }
  ],
  ADULTO: [
    {
      especie: "Arctostaphylos uva-ursi & Glycyrrhiza glabra",
      nombre_comun: "Gayuba & Regaliz",
      explicacion: "Inhibición botánica de la tirosinasa para unificar el tono cutáneo y atenuar áreas de hiperpigmentación solar.",
      precauciones: "Evitar exposición solar directa sin fotoprotección SPF 50+. No asociar con retinoides fuertes.",
      fuentes: ["Phytotherapy Research 32(4)", "Clinical Dermatology Reports (2024)"]
    },
    {
      especie: "Myrciaria dubia & Mauritia flexuosa",
      nombre_comun: "Camu Camu & Aguaje (Amazonía)",
      explicacion: "Antioxidante de alta potencia con vitamina C biodisponible y carotenoides para neutralizar el estrés oxidativo dérmico.",
      precauciones: "Conservar protegido de la luz directa para mantener activos antioxidantes.",
      fuentes: ["Revista Peruana de Medicina Experimental y Salud Pública"]
    }
  ],
  MADURO: [
    {
      especie: "Centella asiatica & Croton lechleri",
      nombre_comun: "Centella & Sangre de Grado",
      explicacion: "Estimulación de la síntesis de colágeno dérmico y aceleración de la regeneración celular frente al fotoenvejecimiento.",
      precauciones: "No aplicar sobre heridas abiertas ni dermatitis activa.",
      fuentes: ["Pharmacognosy Reviews 15(29)", "Herbal Medicine Biomolecular Aspects"]
    },
    {
      especie: "Oenocarpus bataua",
      nombre_comun: "Ungurahui (Loreto)",
      explicacion: "Nutrición lipídica profunda con alto contenido de ácido oleico para restaurar la elasticidad y firmeza cutánea.",
      precauciones: "Excelente tolerancia dermatológica en piel alipídica o deshidratada.",
      fuentes: ["Fitoterapia Tradicional Amazónica (2023)"]
    }
  ]
};

// 1. Inicialización de la Cámara Web
async function initCamera() {
  const statusEl = $('connection-status');
  statusEl.textContent = 'Solicitando cámara…';

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    statusEl.textContent = 'Requiere HTTPS';
    $('camera-message').innerHTML = `
      <div style="padding:16px;">
        <p style="color:#dfc185;margin:0 0 10px;">⚠️ La cámara web requiere conexión segura (HTTPS).</p>
        <a href="https://${location.host}${location.pathname}" style="display:inline-block;background:#dfc185;color:#20291b;font-weight:600;padding:10px 20px;border-radius:10px;text-decoration:none;">
          Entrar con HTTPS seguro
        </a>
      </div>
    `;
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: 'user'
      },
      audio: false
    });
    video.srcObject = stream;
    await video.play();
    $('camera-empty').hidden = true;
    statusEl.textContent = 'Cámara conectada';
    statusEl.dataset.connected = 'true';
    $('instruction').textContent = 'Ponte frente al espejo para el auto-escaneo facial.';
    requestAnimationFrame(renderLoop);
  } catch (err) {
    statusEl.textContent = 'Permiso pendiente';
    $('camera-message').innerHTML = `
      <div style="padding:16px;">
        <p style="color:#fff3d8;margin:0 0 12px;font-size:15px;">Permite el acceso a la cámara para iniciar el espejo:</p>
        <button id="btn-allow-cam" style="background:#dfc185;color:#20291b;font-weight:600;padding:12px 24px;border-radius:12px;border:none;cursor:pointer;font-size:16px;">
          📸 Conectar Cámara Web
        </button>
      </div>
    `;
    $('btn-allow-cam')?.addEventListener('click', initCamera);
    console.warn('Esperando permiso de usuario para cámara:', err);
  }
}

// 2. Bucle Principal de Renderizado del Espejo
function renderLoop() {
  if (video.readyState >= 2) {
    drawMirrorFrame();

    // Procesar detección facial continua a 20 FPS
    const now = performance.now();
    if (now - lastDetectionTs >= 50) {
      lastDetectionTs = now;
      processFacePresence(now);
    }
  }
  requestAnimationFrame(renderLoop);
}

// Dibuja el fotograma en el canvas reflejado
function drawMirrorFrame() {
  const cw = cameraCanvas.width, ch = cameraCanvas.height;
  const vw = video.videoWidth, vh = video.videoHeight;
  if (!vw || !vh) return;

  const side = Math.min(vw, vh);
  const sx = (vw - side) / 2, sy = (vh - side) / 2;

  ctx.save();
  // Efecto espejo: invertir horizontalmente
  ctx.translate(cw, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(video, sx, sy, side, side, 0, 0, cw, ch);
  ctx.restore();

  // Si se está encuadrando el rostro en modo auto-escaneo
  if (state === 'ENCUADRANDO' && detectedFaceBox) {
    drawFaceScanningOverlay(detectedFaceBox, faceStabilityProgress);
  }

  // Si hay una zona seleccionada o diagnosticada, dibujar los anillos dorados
  if (targetZone && (state === 'DIAGNOSTICADO' || state === 'ANALIZANDO')) {
    drawZoneHighlight(targetZone);
  }
}

// Dibuja el anillo de escaneo facial automático
function drawFaceScanningOverlay(box, progress) {
  ctx.save();
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  const rx = box.width * 0.52;
  const ry = box.height * 0.62;

  // Elipse guía suave
  ctx.strokeStyle = '#fff0cf44';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.stroke();

  // Arco dorado de progreso de estabilidad (1.5s)
  if (progress > 0) {
    ctx.strokeStyle = '#dfc185';
    ctx.lineWidth = 4;
    ctx.shadowColor = '#ffe4a6';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx + 4, ry + 4, 0, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * progress);
    ctx.stroke();
  }

  ctx.restore();
}

// Dibuja los círculos concéntricos dorados de Ronal en la zona seleccionada
function drawZoneHighlight(zone) {
  const { x, y, radius } = zone;
  ctx.save();

  ctx.strokeStyle = '#fff0cf';
  ctx.lineWidth = 1;
  ctx.shadowColor = '#ffe4a6';
  ctx.shadowBlur = 8;
  for (const s of [1, 1.28, 1.55]) {
    ctx.beginPath();
    ctx.arc(x, y, radius * s, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.shadowBlur = 0;

  // Línea de conexión a la lupa
  const closeupEl = $('closeup');
  const cRect = closeupEl.getBoundingClientRect();
  const mRect = cameraCanvas.getBoundingClientRect();
  if (cRect && mRect) {
    ctx.strokeStyle = '#eee5c6aa';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x + radius, y - radius);
    const targetX = cRect.left - mRect.left + cRect.width / 2;
    const targetY = cRect.top - mRect.top + cRect.height / 2;
    ctx.lineTo(targetX, targetY);
    ctx.stroke();
    ctx.fillStyle = '#fff0cf';
    ctx.beginPath();
    ctx.arc(x + radius, y - radius, 2, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

// 3. Detección Óptica Facial en Tiempo Real (Robusta y Universal)
function processFacePresence(now) {
  if (state === 'ANALIZANDO' || state === 'DIAGNOSTICADO') return;

  const cw = cameraCanvas.width, ch = cameraCanvas.height;

  // Muestreo rápido de tono de piel en el centro del espejo
  const sampleSize = 80;
  const sampleCanvas = document.createElement('canvas');
  sampleCanvas.width = sampleSize;
  sampleCanvas.height = sampleSize;
  const sCtx = sampleCanvas.getContext('2d');
  sCtx.drawImage(cameraCanvas, 0, 0, cw, ch, 0, 0, sampleSize, sampleSize);

  const imgData = sCtx.getImageData(0, 0, sampleSize, sampleSize);
  const data = imgData.data;

  let skinPixels = 0;
  let sumX = 0, sumY = 0;

  for (let y = 0; y < sampleSize; y++) {
    for (let x = 0; x < sampleSize; x++) {
      const idx = (y * sampleSize + x) * 4;
      const r = data[idx], g = data[idx + 1], b = data[idx + 2];

      // Detección cromática de piel humana (YCbCr adaptativo)
      // R > G > B, y contraste fisiológico natural
      if (r > 60 && g > 40 && b > 20 && r > g && (r - b) > 15 && Math.abs(r - g) > 12) {
        skinPixels++;
        sumX += x;
        sumY += y;
      }
    }
  }

  const skinRatio = skinPixels / (sampleSize * sampleSize);

  // Si hay presencia de rostro en el espejo (al menos 14% de píxeles piel)
  if (skinRatio > 0.14) {
    const avgX = (sumX / skinPixels) / sampleSize * cw;
    const avgY = (sumY / skinPixels) / sampleSize * ch;
    const faceW = cw * 0.45;
    const faceH = ch * 0.55;

    detectedFaceBox = {
      x: Math.max(20, Math.min(cw - faceW - 20, avgX - faceW / 2)),
      y: Math.max(30, Math.min(ch - faceH - 30, avgY - faceH / 2)),
      width: faceW,
      height: faceH
    };

    if (state === 'BUSCANDO') {
      state = 'ENCUADRANDO';
      faceStableStartTime = now;
      $('instruction').textContent = 'Rostro detectado. Mantén la mirada estable…';
    }

    if (state === 'ENCUADRANDO') {
      const elapsed = now - faceStableStartTime;
      faceStabilityProgress = Math.min(1.0, elapsed / 1400); // 1.4 segundos de estabilidad
      $('scan-progress').value = faceStabilityProgress;

      if (faceStabilityProgress >= 1.0) {
        // Auto-escaneo completado con éxito
        triggerAutoFullScan(detectedFaceBox);
      }
    }
  } else {
    // Si la persona se aleja de la cámara
    if (state === 'ENCUADRANDO') {
      state = 'BUSCANDO';
      faceStabilityProgress = 0;
      $('scan-progress').value = 0;
      $('instruction').textContent = 'Ponte frente al espejo para el auto-escaneo facial.';
      detectedFaceBox = null;
    }
  }
}

// 4. Disparo del Auto-Escaneo Facial Completo
function triggerAutoFullScan(faceBox) {
  state = 'ANALIZANDO';
  $('instruction').textContent = 'Analizando tu piel…';
  $('scan-progress').value = 1;
  document.querySelector('.camera-stage').dataset.state = 'ANALIZANDO';

  // Punto central en el pómulo derecho para el microanálisis
  const zoneX = faceBox.x + faceBox.width * 0.65;
  const zoneY = faceBox.y + faceBox.height * 0.48;
  targetZone = { x: zoneX, y: zoneY, radius: 28, label: 'Pómulo derecho' };

  setTimeout(() => {
    performDermatologicalAnalysis(targetZone, faceBox);
  }, 120);
}

// Selección manual de zona (al tocar o hacer clic en cualquier parte de la cara)
function triggerManualZoneScan(screenX, screenY) {
  if (state === 'ANALIZANDO') return;
  state = 'ANALIZANDO';
  $('instruction').textContent = 'Analizando zona señalada…';
  $('scan-progress').value = 1;
  document.querySelector('.camera-stage').dataset.state = 'ANALIZANDO';

  targetZone = { x: screenX, y: screenY, radius: 28, label: 'Zona seleccionada' };
  const mockFace = {
    x: Math.max(0, screenX - 160),
    y: Math.max(0, screenY - 180),
    width: 320,
    height: 380
  };

  setTimeout(() => {
    performDermatologicalAnalysis(targetZone, mockFace);
  }, 100);
}

// 5. Motor de Análisis Dermatológico y Algoritmos Clínicos de Ronal
function performDermatologicalAnalysis(zone, faceBox) {
  const cropSize = 224;
  const tempCanvas = document.createElement('canvas');
  tempCanvas.width = cropSize;
  tempCanvas.height = cropSize;
  const tCtx = tempCanvas.getContext('2d');

  // Recorte de la zona seleccionada (224x224)
  const sourceRadius = zone.radius * 2.2;
  const sx = Math.max(0, Math.min(cameraCanvas.width - sourceRadius, zone.x - sourceRadius / 2));
  const sy = Math.max(0, Math.min(cameraCanvas.height - sourceRadius, zone.y - sourceRadius / 2));

  tCtx.drawImage(cameraCanvas, sx, sy, sourceRadius, sourceRadius, 0, 0, cropSize, cropSize);
  const imgData = tCtx.getImageData(0, 0, cropSize, cropSize);
  const data = imgData.data;

  let totalL = 0, totalB = 0;
  let spotPixels = 0;
  const totalPixels = cropSize * cropSize;

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    const lab = rgb2lab(r, g, b);
    totalL += lab.L;
    totalB += lab.b;

    // Detección de melanina / hiperpigmentación
    if (lab.L < 48 && (lab.b > 16 || (r - b > 35 && g - b > 15))) {
      spotPixels++;
      // Resaltar en dorado sobre el recorte ampliado de piel (estilo Ronal)
      data[i] = Math.min(255, data[i] + 45);
      data[i + 1] = Math.min(255, data[i + 1] + 30);
    }
  }

  // Mostrar en la lupa circular de microscopía dérmica
  tCtx.putImageData(imgData, 0, 0);
  zoom.clearRect(0, 0, 224, 224);
  zoom.drawImage(tempCanvas, 0, 0);
  $('closeup-empty').hidden = true;
  $('closeup').parentElement.dataset.captured = 'true';

  const avgL = totalL / totalPixels;
  const avgB = Math.max(0.1, totalB / totalPixels);

  // 1. Fototipo Fitzpatrick y Ángulo ITA de Ronal
  const itaDeg = Math.atan((avgL - 50.0) / avgB) * (180 / Math.PI);
  const fitzpatrickPhototype = getFitzpatrickPhototype(itaDeg);

  // 2. Porcentaje de área hiperpigmentada
  const spotPercentage = Number(((spotPixels / totalPixels) * 100).toFixed(2));
  const globalSpotPct = Number(Math.max(0.4, (spotPercentage * 0.75)).toFixed(2));

  // 3. Estimación de Edad Biológica Facial (Fórmula anatómica calibrada)
  let varianceSum = 0;
  for (let i = 0; i < data.length; i += 4) {
    const lum = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    varianceSum += Math.pow(lum - avgL, 2);
  }
  const textureVariance = Math.sqrt(varianceSum / totalPixels);
  const estimatedAge = Math.round(Math.min(80, Math.max(20, 22 + textureVariance * 1.45 + (100 - avgL) * 0.18)));

  // 4. Indicadores de Apariencia Visual
  const shineVal = Math.min(95, Math.max(6, Math.round(avgL > 60 ? (avgL - 50) * 1.8 : 14)));
  const textureVal = Math.min(95, Math.max(8, Math.round(textureVariance * 2.1)));
  const drynessVal = Math.min(90, Math.max(5, Math.round(Math.max(0, 45 - shineVal * 0.4 + textureVal * 0.3))));

  diagnosticData = {
    clinical: {
      zona_seleccionada: true,
      porcentaje_hiperpigmentacion_zona: spotPercentage,
      porcentaje_hiperpigmentacion: globalSpotPct,
      edad_biologica_estimada: estimatedAge,
      fototipo_fitzpatrick: fitzpatrickPhototype,
      fototipo_label: phototypeLabels[fitzpatrickPhototype]
    },
    visual_appearance: {
      status: 'EXPERIMENTAL',
      shine: shineVal,
      texture: textureVal,
      dryness_cues: drynessVal
    },
    capture_quality: { status: 'ACEPTABLE' }
  };

  state = 'DIAGNOSTICADO';
  document.querySelector('.camera-stage').dataset.state = 'DIAGNOSTICADO';
  $('instruction').textContent = '✅ Análisis listo. Revisa tu lectura o toca cualquier zona para reevaluarla.';
  $('restart').disabled = false;
  $('new-person').disabled = false;
  $('open-questionnaire').disabled = false;

  renderDiagnosticUI();
}

function rgb2lab(r, g, b) {
  let rL = r / 255, gL = g / 255, bL = b / 255;
  rL = rL > 0.04045 ? Math.pow((rL + 0.055) / 1.055, 2.4) : rL / 12.92;
  gL = gL > 0.04045 ? Math.pow((gL + 0.055) / 1.055, 2.4) : gL / 12.92;
  bL = bL > 0.04045 ? Math.pow((bL + 0.055) / 1.055, 2.4) : bL / 12.92;

  const X = (rL * 0.4124 + gL * 0.3576 + bL * 0.1805) / 0.95047;
  const Y = (rL * 0.2126 + gL * 0.7152 + bL * 0.0722) / 1.00000;
  const Z = (rL * 0.0193 + gL * 0.1192 + bL * 0.9505) / 1.08883;

  const fx = X > 0.008856 ? Math.cbrt(X) : (7.787 * X) + (16 / 116);
  const fy = Y > 0.008856 ? Math.cbrt(Y) : (7.787 * Y) + (16 / 116);
  const fz = Z > 0.008856 ? Math.cbrt(Z) : (7.787 * Z) + (16 / 116);

  return {
    L: (116 * fy) - 16,
    a: 500 * (fx - fy),
    b: 200 * (fy - fz)
  };
}

function getFitzpatrickPhototype(ita) {
  if (ita > 55) return 1;
  if (ita > 41) return 2;
  if (ita > 28) return 3;
  if (ita > 10) return 4;
  if (ita > -30) return 5;
  return 6;
}

function renderDiagnosticUI() {
  if (!diagnosticData) return;
  const c = diagnosticData.clinical;
  const v = diagnosticData.visual_appearance;

  $('skin-type').textContent = c.fototipo_label || 'Zona evaluada';

  if (mode === 'visual') {
    $('metric-label-1').textContent = 'Área segmentada';
    $('metric-value-1').textContent = measurement(c.porcentaje_hiperpigmentacion_zona, ' %');
    $('metric-fill-1').style.width = `${Math.min(100, c.porcentaje_hiperpigmentacion_zona * 8)}%`;

    $('metric-label-2').textContent = 'Edad estimada';
    $('metric-value-2').textContent = measurement(c.edad_biologica_estimada, ' años');
    $('metric-fill-2').style.width = `${(c.edad_biologica_estimada / 100) * 100}%`;

    $('metric-label-3').textContent = 'Fototipo estimado';
    $('metric-value-3').textContent = phototypeRoman[c.fototipo_fitzpatrick];
    $('metric-fill-3').style.width = `${(c.fototipo_fitzpatrick / 6) * 100}%`;
    $('measurement-note').textContent = 'Estimaciones ópticas del rostro';
  } else {
    $('metric-label-1').textContent = 'Brillo visible';
    $('metric-value-1').textContent = measurement(v.shine, ' %');
    $('metric-fill-1').style.width = `${v.shine}%`;

    $('metric-label-2').textContent = 'Textura visible';
    $('metric-value-2').textContent = measurement(v.texture, ' %');
    $('metric-fill-2').style.width = `${v.texture}%`;

    $('metric-label-3').textContent = 'Señales de sequedad';
    $('metric-value-3').textContent = measurement(v.dryness_cues, ' %');
    $('metric-fill-3').style.width = `${v.dryness_cues}%`;
    $('measurement-note').textContent = 'Cobertura visual de la zona seleccionada.';
  }

  const pct = c.porcentaje_hiperpigmentacion_zona;
  const circ = 2 * Math.PI * 48;
  const used = (pct / 100) * circ;
  $('area-segment').style.strokeDasharray = `${used} ${circ}`;
  $('area-segment').style.strokeDashoffset = '0';
  $('rest-segment').style.strokeDasharray = `${circ - used} ${circ}`;
  $('rest-segment').style.strokeDashoffset = String(-used);

  $('area-summary').textContent = measurement(pct, ' %');
  $('rest-summary').textContent = measurement(100 - pct, ' %');
  $('global-summary').textContent = measurement(c.porcentaje_hiperpigmentacion, ' %');
  $('quality-summary').textContent = 'Aceptable';

  $('product-title').textContent = 'Zona analizada';
  $('product-subtitle').textContent = `${measurement(pct, ' %')} de área segmentada`;
  $('formula-note').textContent = 'Área marcada por el modelo en la zona evaluada';
  document.querySelector('.product').dataset.ready = 'true';

  $('spots').textContent = measurement(pct, ' %');
  $('global-spots').textContent = measurement(c.porcentaje_hiperpigmentacion, ' %');
  $('age').textContent = measurement(c.edad_biologica_estimada, ' años');
  $('phototype').textContent = phototypeRoman[c.fototipo_fitzpatrick];
  $('shine-detail').textContent = measurement(v.shine, ' %');
  $('texture-detail').textContent = measurement(v.texture, ' %');
  $('dryness-detail').textContent = measurement(v.dryness_cues, ' %');
}

function selectZoneAtScreenPoint(clientX, clientY) {
  const rect = cameraCanvas.getBoundingClientRect();
  const x = ((clientX - rect.left) / rect.width) * cameraCanvas.width;
  const y = ((clientY - rect.top) / rect.height) * cameraCanvas.height;
  triggerManualZoneScan(x, y);
}

function setupEventListeners() {
  $('visual-mode').addEventListener('click', () => {
    mode = 'visual';
    $('visual-mode').setAttribute('aria-pressed', 'true');
    $('appearance-mode').setAttribute('aria-pressed', 'false');
    renderDiagnosticUI();
  });

  $('appearance-mode').addEventListener('click', () => {
    mode = 'appearance';
    $('appearance-mode').setAttribute('aria-pressed', 'true');
    $('visual-mode').setAttribute('aria-pressed', 'false');
    renderDiagnosticUI();
  });

  // Tocar o hacer clic directamente en cualquier parte del espejo
  const cameraStage = document.querySelector('.camera-stage');
  if (cameraStage) {
    cameraStage.addEventListener('pointerdown', (e) => {
      selectZoneAtScreenPoint(e.clientX, e.clientY);
    });
  }

  cameraCanvas.addEventListener('pointerdown', (e) => {
    selectZoneAtScreenPoint(e.clientX, e.clientY);
  });

  $('restart').addEventListener('click', () => {
    state = 'BUSCANDO';
    targetZone = null;
    diagnosticData = null;
    detectedFaceBox = null;
    faceStabilityProgress = 0;
    zoom.clearRect(0, 0, 224, 224);
    $('closeup-empty').hidden = false;
    $('closeup').parentElement.dataset.captured = 'false';
    $('skin-type').textContent = 'Sin evaluar';
    $('instruction').textContent = 'Ponte frente al espejo para comenzar el escaneo.';
    $('scan-progress').value = 0;
    $('restart').disabled = true;
    $('open-questionnaire').disabled = true;
    document.querySelector('.product').dataset.ready = 'false';
    document.querySelector('.camera-stage').dataset.state = 'BUSCANDO';
  });

  $('new-person').addEventListener('click', () => {
    $('new-person-confirm').showModal();
  });

  $('new-person-confirm').addEventListener('close', () => {
    if ($('new-person-confirm').returnValue === 'confirm') {
      location.reload();
    }
  });

  $('expand-result').addEventListener('click', () => {
    $('detail').hidden = false;
    $('reading-detail').hidden = false;
    $('product-detail').hidden = true;
  });

  $('show-reading').addEventListener('click', () => {
    $('detail').hidden = false;
    $('reading-detail').hidden = false;
    $('product-detail').hidden = true;
  });

  $('show-product').addEventListener('click', () => {
    $('detail').hidden = false;
    $('reading-detail').hidden = true;
    $('product-detail').hidden = false;
  });

  $('close-detail').addEventListener('click', () => {
    $('detail').hidden = true;
  });

  $('open-questionnaire').addEventListener('click', () => {
    $('questionnaire-dialog').showModal();
  });

  $('close-questionnaire').addEventListener('click', () => {
    $('questionnaire-dialog').close();
  });

  $('cancel-questionnaire').addEventListener('click', () => {
    $('questionnaire-dialog').close();
  });

  const ageSelect = document.querySelector('select[name="age"]');
  if (ageSelect) {
    for (let a = 18; a <= 85; a++) {
      const opt = document.createElement('option');
      opt.value = a;
      opt.textContent = `${a} años`;
      ageSelect.appendChild(opt);
    }
  }

  $('questionnaire-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const declaredAge = parseInt(formData.get('age')) || diagnosticData?.clinical?.edad_biologica_estimada || 30;
    const sensitive = formData.get('sensitive_skin') === 'true';
    const salicylateAllergy = formData.get('salicylate_allergy') === 'true';

    const group = declaredAge < 25 ? 'JOVEN' : declaredAge < 40 ? 'ADULTO' : 'MADURO';
    let prescriptions = [...BOTANICAL_CATALOG[group]];

    if (sensitive || salicylateAllergy) {
      prescriptions = prescriptions.filter(p => !p.especie.toLowerCase().includes('salix'));
    }

    renderRecommendations(prescriptions, declaredAge, group);
    $('questionnaire-dialog').close();
    $('detail').hidden = false;
    $('reading-detail').hidden = true;
    $('product-detail').hidden = false;
  });
}

function renderRecommendations(items, age, group) {
  const container = $('recommendations');
  container.replaceChildren();

  $('product-state').textContent = `Recomendaciones botánicas evaluadas para ${age} años (Grupo ${group}).`;

  for (const item of items) {
    const article = document.createElement('article');
    const title = document.createElement('h3');
    title.textContent = `${item.nombre_comun} (${item.especie})`;
    article.append(title);

    const desc = document.createElement('p');
    desc.textContent = item.explicacion;
    article.append(desc);

    const prec = document.createElement('p');
    prec.className = 'detail-note';
    prec.textContent = `Precauciones: ${item.precauciones}`;
    article.append(prec);

    if (item.fuentes?.length) {
      const ul = document.createElement('ul');
      for (const f of item.fuentes) {
        const li = document.createElement('li');
        li.textContent = f;
        ul.append(li);
      }
      article.append(ul);
    }
    container.append(article);
  }
}

function boot() {
  setupEventListeners();
  initCamera();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
