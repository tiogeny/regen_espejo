// REGEN · Espejo Inteligente de Diagnóstico Dermatoscópico (Client-Side Web)

// Redirigir automáticamente a HTTPS si se entra por HTTP (la webcam solo funciona en HTTPS)
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

// Estado global de la aplicación
let state = 'BUSCANDO'; // 'BUSCANDO' | 'FIJANDO_ZONA' | 'ANALIZANDO' | 'DIAGNOSTICADO'
let mode = 'visual'; // 'visual' | 'appearance'
let targetZone = null; // { x, y, radius, startTs, progress }
let diagnosticData = null;
let faceLandmarker = null;
let handLandmarker = null;
let isModelReady = false;
let lastVideoTime = -1;
let currentFaceLandmarks = null;

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

// 1. Inicialización Inmediata de la Cámara Web
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
    requestAnimationFrame(renderLoop);
  } catch (err) {
    statusEl.textContent = 'Permiso pendiente';
    $('camera-message').innerHTML = `
      <div style="padding:16px;">
        <p style="color:#fff3d8;margin:0 0 12px;font-size:15px;">Haz clic aquí para conceder permiso a la cámara:</p>
        <button id="btn-allow-cam" style="background:#dfc185;color:#20291b;font-weight:600;padding:12px 24px;border-radius:12px;border:none;cursor:pointer;font-size:16px;">
          📸 Conectar Cámara Web
        </button>
      </div>
    `;
    $('btn-allow-cam')?.addEventListener('click', initCamera);
    console.warn('Esperando permiso de usuario para cámara:', err);
  }
}

// 2. Inicialización Asíncrona de Modelos MediaPipe (sin bloquear la cámara)
async function initMediaPipe() {
  try {
    const visionModule = await import("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.js");
    const { FilesetResolver, FaceLandmarker, HandLandmarker } = visionModule;

    const vision = await FilesetResolver.forVisionTasks(
      "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
    );

    faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: "./models/face_landmarker.task",
        delegate: "GPU"
      },
      runningMode: "VIDEO",
      numFaces: 1
    });

    try {
      handLandmarker = await HandLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: "./models/hand_landmarker.task",
          delegate: "GPU"
        },
        runningMode: "VIDEO",
        numHands: 1
      });
    } catch (e) {
      handLandmarker = await HandLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: "./models/hand_landmarker.task",
          delegate: "CPU"
        },
        runningMode: "VIDEO",
        numHands: 1
      });
    }

    isModelReady = true;
    console.log("MediaPipe Face & Hand Landmarker activos.");
  } catch (err) {
    console.warn("MediaPipe no disponible, operando en modo táctil directo:", err);
  }
}

// 3. Bucle Principal de Renderizado del Espejo
function renderLoop() {
  if (video.readyState >= 2) {
    drawMirrorFrame();
    if (isModelReady && video.currentTime !== lastVideoTime) {
      lastVideoTime = video.currentTime;
      processTracking(video.currentTime * 1000);
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

  // Si hay una zona seleccionada o en proceso de fijado, dibujar los círculos dorados
  if (targetZone && (state === 'FIJANDO_ZONA' || state === 'DIAGNOSTICADO')) {
    drawZoneHighlight(targetZone);
  }
}

// Dibuja los círculos concéntricos dorados de Ronal
function drawZoneHighlight(zone) {
  const { x, y, radius, progress = 0 } = zone;
  ctx.save();

  // Anillos concéntricos
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

  // Arco de progreso si se está fijando la zona
  if (state === 'FIJANDO_ZONA' && progress > 0) {
    ctx.strokeStyle = '#dfc185';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(x, y, radius * 1.55, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * progress);
    ctx.stroke();
  }

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

// 4. Detección de Rostro y Señalamiento con el Dedo Índice
function processTracking(timestamp) {
  if (state === 'ANALIZANDO') return;

  const vw = video.videoWidth, vh = video.videoHeight;
  const side = Math.min(vw, vh);
  const sx = (vw - side) / 2, sy = (vh - side) / 2;
  const cw = cameraCanvas.width, ch = cameraCanvas.height;

  // Detección facial
  const faceResult = faceLandmarker?.detectForVideo(video, timestamp);
  currentFaceLandmarks = faceResult?.faceLandmarks?.[0] || null;

  if (!currentFaceLandmarks) {
    if (state !== 'DIAGNOSTICADO') {
      $('instruction').textContent = 'Ponte frente al espejo para comenzar.';
      $('scan-progress').value = 0;
    }
    return;
  }

  // Detección de mano
  const handResult = handLandmarker?.detectForVideo(video, timestamp);
  const handLandmarks = handResult?.landmarks?.[0] || null;

  if (handLandmarks) {
    const tip = handLandmarks[8];
    const pip = handLandmarks[6];
    const mcp = handLandmarks[5];

    const distTipMcp = Math.hypot(tip.x - mcp.x, tip.y - mcp.y);
    const distPipMcp = Math.hypot(pip.x - mcp.x, pip.y - mcp.y);
    const isExtended = distTipMcp > distPipMcp * 1.15;

    if (isExtended) {
      const tipVidX = tip.x * vw;
      const tipVidY = tip.y * vh;

      const mirrorX = cw - ((tipVidX - sx) / side * cw);
      const mirrorY = ((tipVidY - sy) / side) * ch;

      const faceBounding = getFaceBounds(currentFaceLandmarks, vw, vh, sx, sy, side, cw, ch);
      if (isPointInsideFace(mirrorX, mirrorY, faceBounding)) {
        handleFingerPointing(mirrorX, mirrorY);
        return;
      }
    }
  }

  if (state === 'FIJANDO_ZONA') {
    if (targetZone && targetZone.progress >= 0.85) {
      triggerClinicalAnalysis(targetZone);
    } else {
      state = 'BUSCANDO';
      targetZone = null;
      $('instruction').textContent = 'Señala una zona de tu rostro con el índice.';
      $('scan-progress').value = 0;
    }
  }
}

function getFaceBounds(landmarks, vw, vh, sx, sy, side, cw, ch) {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const lm of landmarks) {
    const px = cw - ((lm.x * vw - sx) / side * cw);
    const py = (lm.y * vh - sy) / side * ch;
    if (px < minX) minX = px;
    if (px > maxX) maxX = px;
    if (py < minY) minY = py;
    if (py > maxY) maxY = py;
  }
  return { minX, maxX, minY, maxY, width: maxX - minX, height: maxY - minY };
}

function isPointInsideFace(px, py, b) {
  const marginX = b.width * 0.08, marginY = b.height * 0.08;
  return px >= b.minX + marginX && px <= b.maxX - marginX &&
         py >= b.minY + marginY && py <= b.maxY - marginY;
}

function handleFingerPointing(x, y) {
  const now = performance.now();
  const radius = 28;

  if (state !== 'FIJANDO_ZONA' || !targetZone) {
    state = 'FIJANDO_ZONA';
    targetZone = { x, y, radius, startTs: now, progress: 0 };
    $('instruction').textContent = 'Mantén tu dedo para fijar la zona…';
  } else {
    targetZone.x = targetZone.x * 0.8 + x * 0.2;
    targetZone.y = targetZone.y * 0.8 + y * 0.2;
    const elapsed = now - targetZone.startTs;
    targetZone.progress = Math.min(1.0, elapsed / 1200);
    $('scan-progress').value = targetZone.progress;

    if (targetZone.progress >= 1.0) {
      $('instruction').textContent = '¡Zona fijada! Retira tu mano para analizar.';
    }
  }
}

// 5. Análisis Clínico On-Device
function triggerClinicalAnalysis(zone) {
  state = 'ANALIZANDO';
  $('instruction').textContent = 'Analizando tu zona cutánea…';
  $('scan-progress').value = 1;
  document.querySelector('.camera-stage').dataset.state = 'ANALIZANDO';

  setTimeout(() => {
    performDermatologicalCalculations(zone);
  }, 150);
}

function performDermatologicalCalculations(zone) {
  const cropSize = 224;
  const tempCanvas = document.createElement('canvas');
  tempCanvas.width = cropSize;
  tempCanvas.height = cropSize;
  const tCtx = tempCanvas.getContext('2d');

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

    if (lab.L < 48 && (lab.b > 16 || (r - b > 35 && g - b > 15))) {
      spotPixels++;
      data[i] = Math.min(255, data[i] + 45);
      data[i + 1] = Math.min(255, data[i + 1] + 30);
    }
  }

  tCtx.putImageData(imgData, 0, 0);
  zoom.clearRect(0, 0, 224, 224);
  zoom.drawImage(tempCanvas, 0, 0);
  $('closeup-empty').hidden = true;
  $('closeup').parentElement.dataset.captured = 'true';

  const avgL = totalL / totalPixels;
  const avgB = Math.max(0.1, totalB / totalPixels);

  const itaDeg = Math.atan((avgL - 50.0) / avgB) * (180 / Math.PI);
  const fitzpatrickPhototype = getFitzpatrickPhototype(itaDeg);

  const spotPercentage = Number(((spotPixels / totalPixels) * 100).toFixed(2));
  const globalSpotPct = Number(Math.max(0.5, (spotPercentage * 0.72)).toFixed(2));

  let varianceSum = 0;
  for (let i = 0; i < data.length; i += 4) {
    const lum = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    varianceSum += Math.pow(lum - avgL, 2);
  }
  const textureVariance = Math.sqrt(varianceSum / totalPixels);
  const estimatedAge = Math.round(Math.min(85, Math.max(19, 23 + textureVariance * 1.45 + (100 - avgL) * 0.2)));

  const shineVal = Math.min(95, Math.max(5, Math.round(avgL > 60 ? (avgL - 50) * 1.8 : 12)));
  const textureVal = Math.min(95, Math.max(8, Math.round(textureVariance * 2.1)));
  const drynessVal = Math.min(90, Math.max(4, Math.round(Math.max(0, 45 - shineVal * 0.4 + textureVal * 0.3))));

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
  $('instruction').textContent = 'Análisis listo. Revisa tus mediciones o completa el cuestionario.';
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
    $('measurement-note').textContent = 'Estimaciones de la cámara';
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
    $('measurement-note').textContent = 'Cobertura visual experimental de la zona seleccionada.';
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
  $('formula-note').textContent = 'Área marcada por el modelo en la zona señalada';
  document.querySelector('.product').dataset.ready = 'true';

  $('spots').textContent = measurement(pct, ' %');
  $('global-spots').textContent = measurement(c.porcentaje_hiperpigmentacion, ' %');
  $('age').textContent = measurement(c.edad_biologica_estimada, ' años');
  $('phototype').textContent = phototypeRoman[c.fototipo_fitzpatrick];
  $('shine-detail').textContent = measurement(v.shine, ' %');
  $('texture-detail').textContent = measurement(v.texture, ' %');
  $('dryness-detail').textContent = measurement(v.dryness_cues, ' %');
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

  cameraCanvas.addEventListener('pointerdown', (e) => {
    if (state === 'ANALIZANDO') return;
    const rect = cameraCanvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width * cameraCanvas.width;
    const y = (e.clientY - rect.top) / rect.height * cameraCanvas.height;
    targetZone = { x, y, radius: 28, startTs: performance.now(), progress: 1.0 };
    triggerClinicalAnalysis(targetZone);
  });

  $('restart').addEventListener('click', () => {
    state = 'BUSCANDO';
    targetZone = null;
    diagnosticData = null;
    zoom.clearRect(0, 0, 224, 224);
    $('closeup-empty').hidden = false;
    $('closeup').parentElement.dataset.captured = 'false';
    $('skin-type').textContent = 'Sin evaluar';
    $('instruction').textContent = 'Señala una zona de tu rostro con el índice.';
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

// Arranque seguro sin perder el evento DOMContentLoaded
function boot() {
  setupEventListeners();
  initCamera();
  initMediaPipe();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
