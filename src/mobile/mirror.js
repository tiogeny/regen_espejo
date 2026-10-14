'use strict';
const $ = id => document.getElementById(id);
const camera = $('camera'), ctx = camera.getContext('2d');
const closeup = $('closeup'), zoom = closeup.getContext('2d');
let snapshot = null, frameTimer = null, statusTimer = null, restarting = false, framePending = false, statusPending = false;
let mode = 'visual', generation = 0, awaitingRevision = null, pendingSince = 0, actionMessage = '';
let previewId = null, pendingPreviewId = null, capturedImage = null, renderedReadingKey;
const formatter = new Intl.NumberFormat('es-PE', {maximumFractionDigits: 1});
const measurement = (value, unit = '') => Number.isFinite(value) ? formatter.format(value) + unit : '—';
const percentage = value => Number.isFinite(value) && value >= 0 && value <= 100 ? value : null;
const phototype = value => Number.isInteger(value) && value >= 1 && value <= 6 ? ['','I','II','III','IV','V','VI'][value] : '—';
async function request(path, body) {
  const response = await fetch(`/mirror/api/${path}`, {cache: 'no-store', signal: AbortSignal.timeout(5000), ...(body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {})});
  if (!response.ok) {
    let message = response.status === 503 ? 'Esperando cámara…' : 'No se pudo conectar con el espejo.';
    try { const error = await response.json(); if (typeof error.detail === 'string') message = error.detail; } catch {}
    throw new Error(message);
  }
  return response;
}
function clearCaptured() {
  capturedImage?.close(); capturedImage = null; previewId = null; pendingPreviewId = null;
  zoom.clearRect(0, 0, 224, 224); $('closeup').parentElement.dataset.captured = 'false';
}
function clearReading() {
  renderedReadingKey = undefined;
  for (const id of ['spots','global-spots','age','phototype','area-summary','rest-summary','global-summary','quality-summary','shine-detail','texture-detail','dryness-detail']) $(id).textContent = '—';
  $('skin-type').textContent = 'Sin evaluar';
  $('recommendations').replaceChildren();
  $('reading-state').textContent = 'Señala una zona y retira la mano para analizarla.';
  $('reading-quality').textContent = '';
  $('appearance-state').textContent = 'Señala una zona para evaluar su apariencia visual.';
  $('product-title').textContent = 'Lectura de tu piel';
  $('product-subtitle').textContent = 'Señala una zona para comenzar';
  $('formula-note').textContent = 'Sin una lectura todavía';
  document.querySelector('.product').dataset.ready = 'false';
  updateChart(null);
}
function updateChart(value) {
  const length = 2 * Math.PI * 48, used = (value ?? 0) / 100 * length;
  $('area-segment').style.strokeDasharray = `${used} ${length}`;
  $('area-segment').style.strokeDashoffset = '0';
  $('rest-segment').style.strokeDasharray = `${length - used} ${length}`;
  $('rest-segment').style.strokeDashoffset = String(-used);
  document.querySelector('.donut').setAttribute('aria-label', value === null ? 'Esperando una lectura' : `${measurement(value, ' %')} de área segmentada y ${measurement(100 - value, ' %')} restante`);
}
const appearanceMessages = {
  EXPERIMENTAL: 'Cobertura visual experimental de la zona seleccionada.',
  SELECCIONA_ZONA: 'Señala una zona de piel para evaluar su apariencia.',
  SIN_DETALLE: 'Acércate a la cámara y repite la zona para obtener más detalle.',
  LUZ_INADECUADA: 'Ajusta la luz y repite la zona.',
  ZONA_INVALIDA: 'Repite el señalamiento dentro de la mejilla.',
};
function renderMetrics(clinical, value, appearance) {
  const appearanceReady = appearance?.status === 'EXPERIMENTAL';
  const coverage = key => appearanceReady ? percentage(appearance?.[key]) : null;
  const empty = !clinical ? '—' : appearance?.status === 'SIN_DETALLE' ? 'Sin detalle' : 'Repite zona';
  const rows = mode === 'visual' ? [
    [clinical?.zona_seleccionada ? 'Área en zona' : 'Área en rostro', measurement(value, ' %'), value],
    ['Edad estimada', measurement(clinical?.edad_biologica_estimada, ' años'), Number.isFinite(clinical?.edad_biologica_estimada) ? Math.max(0, Math.min(100, clinical.edad_biologica_estimada / 120 * 100)) : null],
    ['Fototipo estimado', phototype(clinical?.fototipo_fitzpatrick), phototype(clinical?.fototipo_fitzpatrick) !== '—' ? clinical.fototipo_fitzpatrick / 6 * 100 : null],
  ] : [['Brillo visible', 'shine'], ['Textura visible', 'texture'], ['Señales de sequedad', 'dryness_cues']].map(([label, key]) => {
    const fill = coverage(key);
    return [label, fill === null ? empty : measurement(fill, ' %'), fill];
  });
  rows.forEach(([label, text, fill], i) => {
    $(`metric-label-${i + 1}`).textContent = label; $(`metric-value-${i + 1}`).textContent = text;
    const track = $(`metric-fill-${i + 1}`).parentElement;
    track.setAttribute('role', 'progressbar'); track.setAttribute('aria-label', label);
    track.setAttribute('aria-valuemin', '0'); track.setAttribute('aria-valuemax', '100');
    track.setAttribute('aria-valuenow', String(fill ?? 0)); track.setAttribute('aria-valuetext', text);
    track.title = i === 1 && mode === 'visual' ? 'Escala: 0 a 120 años' : i === 2 && mode === 'visual' ? 'Escala: fototipos I a VI' : text;
    track.dataset.unavailable = String(fill === null);
    $(`metric-fill-${i + 1}`).style.width = `${fill ?? 0}%`;
  });
  const explanation = appearanceMessages[appearance?.status] || (!clinical ? 'Señala una zona para comenzar.' : 'Repite la zona para obtener el análisis visual.');
  $('measurement-note').textContent = mode === 'visual' ? 'Estimaciones de la cámara' : explanation;
  $('appearance-state').textContent = explanation;
  ['shine-detail', 'texture-detail', 'dryness-detail'].forEach((id, i) => {
    const fill = coverage(['shine', 'texture', 'dryness_cues'][i]);
    $(id).textContent = measurement(fill, ' %');
  });
  $('visual-mode').setAttribute('aria-pressed', String(mode === 'visual'));
  $('appearance-mode').setAttribute('aria-pressed', String(mode === 'appearance'));
}
async function loadCapturedPreview(data) {
  const id = data.analysis_id;
  if (!data.zone_preview_available || !id || previewId === id || pendingPreviewId === id) return;
  pendingPreviewId = id;
  const currentGeneration = generation;
  let image;
  try {
    const response = await request(`analysis-frame?analysis_id=${encodeURIComponent(id)}`);
    image = await createImageBitmap(await response.blob());
    if (generation !== currentGeneration || document.hidden || snapshot?.diagnostic?.analysis_id !== id || awaitingRevision !== null) return;
    capturedImage?.close(); capturedImage = image; image = null; previewId = id;
    zoom.drawImage(capturedImage, 0, 0, 224, 224); $('closeup-empty').hidden = true;
    $('closeup').parentElement.dataset.captured = 'true';
  } catch { /* La lectura sigue visible si la ampliación no está disponible. */ }
  finally { image?.close(); if (pendingPreviewId === id) pendingPreviewId = null; }
}
function render() {
  const connected = snapshot?.connected;
  $('connection-status').textContent = connected ? 'Cámara conectada' : 'Conectando cámara';
  $('connection-status').dataset.connected = String(Boolean(connected));
  document.querySelector('.camera-stage').dataset.state = connected ? snapshot.state : 'DESCONECTADO';
  const data = connected && !restarting && awaitingRevision === null && !snapshot.pending && snapshot.state === 'DIAGNOSTICADO' ? snapshot.diagnostic : null;
  document.querySelector('.mirror-caption').textContent = data ? 'Tu lectura está lista' : snapshot?.state === 'ANALIZANDO' ? 'Analizando la zona seleccionada' : 'Señala una zona para conocer tu piel';
  const clinical = data?.clinical;
  const value = percentage(clinical?.zona_seleccionada ? clinical.porcentaje_hiperpigmentacion_zona : clinical?.porcentaje_hiperpigmentacion);
  const readingKey = JSON.stringify([data, mode]);
  if (readingKey !== renderedReadingKey) {
    clearReading(); renderMetrics(clinical, value, data?.visual_appearance);
    if (clinical) {
      $('spots').textContent = clinical.zona_seleccionada ? measurement(value, ' %') : 'Sin zona seleccionada';
      $('global-spots').textContent = measurement(percentage(clinical.porcentaje_hiperpigmentacion), ' %');
      $('age').textContent = measurement(clinical.edad_biologica_estimada, ' años');
      $('phototype').textContent = phototype(clinical.fototipo_fitzpatrick);
      $('skin-type').textContent = clinical.fototipo_label || 'Zona evaluada';
      $('reading-state').textContent = clinical.zona_seleccionada ? 'Resultado de la zona señalada. La edad y el fototipo se estiman con el rostro.' : 'Resultado del rostro completo.';
      $('product-title').textContent = clinical.zona_seleccionada ? 'Zona analizada' : 'Rostro analizado';
      $('product-subtitle').textContent = value === null ? 'Medición de área no disponible' : `${measurement(value, ' %')} de área segmentada`;
      $('area-summary').textContent = measurement(value, ' %');
      $('rest-summary').textContent = measurement(value === null ? null : 100 - value, ' %');
      $('global-summary').textContent = measurement(percentage(clinical.porcentaje_hiperpigmentacion), ' %');
      $('quality-summary').textContent = data.capture_quality?.status === 'ACEPTABLE' ? 'Aceptable' : 'Sin evaluar';
      $('formula-note').textContent = clinical.zona_seleccionada ? 'Área marcada por el modelo en la zona' : 'Área marcada por el modelo en el rostro';
      $('reading-quality').textContent = data.capture_quality?.status === 'ACEPTABLE' ? 'Captura con exposición aceptable. Resultado automatizado para revisión profesional.' : 'Resultado automatizado para revisión profesional.';
      document.querySelector('.product').dataset.ready = 'true';
      updateChart(value);
      for (const item of data.prescriptions || []) {
        const article = document.createElement('article'), title = document.createElement('h3');
        title.textContent = item.nombre_comun || item.especie || 'Recomendación'; article.append(title);
        for (const text of [item.explicacion, item.precauciones]) {
          if (text) { const p = document.createElement('p'); p.textContent = text; article.append(p); }
        }
        if (Array.isArray(item.fuentes) && item.fuentes.length) {
          const sources = document.createElement('ul');
          for (const source of item.fuentes) {
            const li = document.createElement('li');
            try {
              const url = new URL(source);
              if (!['https:', 'http:'].includes(url.protocol)) throw new Error('invalid source');
              const link = document.createElement('a'); link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = source; li.append(link);
            } catch { li.textContent = source; }
            sources.append(li);
          }
          article.append(sources);
        }
        $('recommendations').append(article);
      }
    } else if (previewId || pendingPreviewId) clearCaptured();
  renderedReadingKey = readingKey;
  }
  if (data) loadCapturedPreview(data);
  renderRecommendationState(data);
  $('instruction').textContent = actionMessage || (!connected ? 'Esperando conexión con la cámara…' : snapshot.pending || awaitingRevision !== null ? 'Preparando una nueva lectura…' : snapshot.state === 'ANALIZANDO' ? 'Analizando tu zona…' : data ? 'Análisis listo. Revisa tu lectura o señala otra zona.' : snapshot.touch?.message || 'Señala una zona del rostro con el índice.');
  $('scan-progress').value = connected ? snapshot.touch?.progress || 0 : 0;
  const disabled = !connected || restarting || awaitingRevision !== null || snapshot.pending || snapshot.state === 'ANALIZANDO';
  $('restart').disabled = $('new-person').disabled = disabled;
}
async function pollStatus() {
  if (document.hidden || statusPending) return;
  statusPending = true;
  const currentGeneration = generation;
  try {
    const next = await (await request('status')).json();
    if (!document.hidden && generation === currentGeneration) {
      snapshot = next;
      if (awaitingRevision !== null && (next.applied_revision === awaitingRevision || next.revision > awaitingRevision)) {
        awaitingRevision = null; actionMessage = '';
      } else if (awaitingRevision !== null && Date.now() - pendingSince > 12000 && !next.pending) {
        awaitingRevision = null; actionMessage = 'El equipo no confirmó el cambio. Revisa la cámara y vuelve a intentarlo.';
      }
    }
  } catch { if (generation === currentGeneration) snapshot = null; }
  finally { statusPending = false; render(); if (!document.hidden) statusTimer = setTimeout(pollStatus, 250); }
}
function clearCamera(message = 'Esperando cámara…') {
  ctx.clearRect(0, 0, camera.width, camera.height); zoom.clearRect(0, 0, 224, 224);
  $('camera-empty').hidden = false; $('camera-message').textContent = message;
  $('closeup-empty').hidden = false;
}
async function pollFrame() {
  if (document.hidden || framePending) return;
  framePending = true;
  const currentGeneration = generation, frameStarted = performance.now();
  let bitmap;
  try {
    const response = await request('frame'); bitmap = await createImageBitmap(await response.blob());
    if (document.hidden || generation !== currentGeneration) return;
    const width = Math.round(camera.clientWidth), height = Math.round(camera.clientHeight);
    if (camera.width !== width || camera.height !== height) { camera.width = width; camera.height = height; }
    const scale = Math.max(width / bitmap.width, height / bitmap.height);
    const offsetX = (width - bitmap.width * scale) / 2, offsetY = (height - bitmap.height * scale) / 2;
    ctx.drawImage(bitmap, offsetX, offsetY, bitmap.width * scale, bitmap.height * scale); $('camera-empty').hidden = true;
    const x = response.headers.get('X-Zone-X'), y = response.headers.get('X-Zone-Y'), radius = response.headers.get('X-Zone-Radius');
    const sourceX = Number(x) * bitmap.width, sourceY = Number(y) * bitmap.height;
    const sourceRadius = Number(radius) * bitmap.width;
    const px = sourceX * scale + offsetX, py = sourceY * scale + offsetY, r = sourceRadius * scale;
    const selected = x !== null && y !== null && radius !== null && Number.isFinite(px) && Number.isFinite(py) && Number.isFinite(r) && Number(x) > 0 && Number(y) > 0 && Number(x) < 1 && Number(y) < 1 && r > 0;
    if (capturedImage) { zoom.drawImage(capturedImage, 0, 0, 224, 224); $('closeup-empty').hidden = true; }
    else {
      zoom.clearRect(0, 0, 224, 224); $('closeup-empty').hidden = selected;
      if (selected) {
        const crop = Math.min(bitmap.width, bitmap.height, Math.max(32, sourceRadius * 2.6));
        zoom.drawImage(bitmap, Math.max(0, Math.min(bitmap.width - crop, sourceX - crop / 2)), Math.max(0, Math.min(bitmap.height - crop, sourceY - crop / 2)), crop, crop, 0, 0, 224, 224);
      }
    }
    if (selected) {
      ctx.strokeStyle = '#fff0cf'; ctx.lineWidth = 1; ctx.shadowColor = '#ffe4a6'; ctx.shadowBlur = 8;
      for (const scale of [1, 1.28, 1.55]) { ctx.beginPath(); ctx.arc(px, py, r * scale, 0, Math.PI * 2); ctx.stroke(); }
      ctx.shadowBlur = 0; ctx.strokeStyle = '#eee5c6aa';
      const target = closeup.getBoundingClientRect(), bounds = camera.getBoundingClientRect();
      ctx.beginPath(); ctx.moveTo(px + r, py - r); ctx.lineTo(target.left - bounds.left, target.top - bounds.top + target.height / 2); ctx.stroke();
      ctx.fillStyle = '#fff0cf'; ctx.beginPath(); ctx.arc(px + r, py - r, 2, 0, Math.PI * 2); ctx.fill();
      if (!capturedImage && snapshot?.touch?.state === 'FIJANDO_ZONA') {
        ctx.strokeStyle = '#e5bc66'; ctx.lineWidth = 3; ctx.beginPath();
        ctx.arc(px, py, r * 1.55, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * Math.max(0, Math.min(1, snapshot.touch.progress))); ctx.stroke();
      }
    }
  } catch (error) { clearCamera(error.message); }
  finally { bitmap?.close(); framePending = false; if (!document.hidden) frameTimer = setTimeout(pollFrame, Math.max(0, 50 - (performance.now() - frameStarted))); }
}
function details(page) {
  $('detail').hidden = false; $('detail-title').textContent = page === 'reading' ? 'Lectura de tu piel' : 'Recomendaciones para tu piel';
  $('appearance-detail').hidden = page !== 'reading';
  $('reading-detail').hidden = page !== 'reading'; $('product-detail').hidden = page !== 'product';
  $('show-reading').setAttribute('aria-expanded', String(page === 'reading'));
  document.querySelectorAll('.pages button').forEach(button => button.classList.toggle('active', button.id === `${page}-page`));
  $('close-detail').focus();
}
function closeDetails() {
  $('detail').hidden = true; $('show-reading').setAttribute('aria-expanded', 'false');
  document.querySelectorAll('.pages button').forEach(button => button.classList.toggle('active', button.id === 'mirror-page'));
}
$('show-reading').onclick = $('reading-page').onclick = $('expand-result').onclick = () => details('reading');
$('show-product').onclick = $('product-page').onclick = () => details('product');
$('close-detail').onclick = $('mirror-page').onclick = closeDetails;
$('visual-mode').onclick = () => { mode = 'visual'; render(); };
$('appearance-mode').onclick = () => { mode = 'appearance'; render(); };
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeDetails(); });
async function restart(newPerson = false) {
  if (!snapshot?.connected || restarting || awaitingRevision !== null) return;
  const revision = snapshot.revision;
  generation++; restarting = true; actionMessage = ''; clearCaptured(); render();
  try {
    await request('restart', {revision, new_person: newPerson});
    awaitingRevision = revision; pendingSince = Date.now(); snapshot = null; clearReading(); closeDetails();
    $('closeup-empty').hidden = false;
  } catch (error) { actionMessage = error.message; }
  finally { restarting = false; render(); }
}
$('restart').onclick = () => restart();
$('new-person').onclick = () => { $('new-person-confirm').returnValue = 'cancel'; $('new-person-confirm').showModal(); };
$('new-person-confirm').addEventListener('close', () => { if ($('new-person-confirm').returnValue === 'confirm') restart(true); });
document.addEventListener('visibilitychange', () => {
  clearTimeout(frameTimer); clearTimeout(statusTimer); generation++;
  if (document.hidden) { snapshot = null; clearCaptured(); clearReading(); clearCamera(); render(); }
  else { pollFrame(); pollStatus(); }
});
const questionnaireDialog = $('questionnaire-dialog'), questionnaireForm = $('questionnaire-form');
let questionnaireAnalysisId = null, recommendationBusy = false, recommendationAttempt = 0, recommendationError = '', recommendationReadingId = null;
const healthQuestions = [
  ['sensitive_skin', '¿Tu piel es sensible?'],
  ['salicylate_allergy', '¿Tienes alergia a la aspirina o a los salicilatos?'],
  ['is_pregnant', '¿Estás embarazada?'],
  ['is_lactating', '¿Estás en período de lactancia?'],
  ['has_open_wounds', '¿Hay heridas abiertas en tu piel?'],
  ['has_cystic_acne', '¿Tienes acné quístico o nódulos profundos?'],
  ['concerning_changes', '¿Alguna mancha cambia, sangra o te preocupa?'],
];
for (const [name, text] of healthQuestions) {
  const label = document.createElement('label'); label.className = 'question'; label.append(text);
  const select = document.createElement('select'); select.name = name; select.required = true;
  for (const [value, caption] of [['', 'Selecciona'], ['no', 'No'], ['yes', 'Sí'], ['unknown', 'No lo sé']]) {
    const option = document.createElement('option'); option.value = value; option.textContent = caption; select.append(option);
  }
  label.dataset.question = name;
  const caption = document.createElement('span'); caption.textContent = text;
  label.replaceChildren(caption, select); $('health-questions').append(label);
}
for (let age = 0; age <= 120; age++) {
  const option = document.createElement('option'); option.value = String(age);
  option.textContent = `${age} años`; questionnaireForm.elements.age.append(option);
}
function updateProfileQuestions() {
  const sex = questionnaireForm.elements.sex.value;
  for (const name of ['is_pregnant', 'is_lactating']) {
    const select = questionnaireForm.elements[name], female = sex === 'female';
    select.closest('.question').hidden = !female;
    select.disabled = !female; select.required = female;
    if (!female) select.value = '';
  }
  document.querySelector('[data-question="sensitive_skin"] span').textContent = sex === 'male'
    ? '¿Tu piel es sensible o se irrita al afeitarte?'
    : '¿Tu piel es sensible?';
}
questionnaireForm.elements.sex.addEventListener('change', () => {
  questionnaireForm.elements.sensitive_skin.value = '';
  questionnaireForm.elements.is_pregnant.value = '';
  questionnaireForm.elements.is_lactating.value = '';
  updateProfileQuestions();
});
updateProfileQuestions();
function resetQuestionnaire() {
  recommendationAttempt++; recommendationBusy = false; questionnaireAnalysisId = null;
  questionnaireForm.reset(); updateProfileQuestions(); $('questionnaire-error').hidden = true;
  $('submit-questionnaire').disabled = false; $('submit-questionnaire').textContent = 'Evaluar recomendaciones';
  if (questionnaireDialog.open) questionnaireDialog.close();
}
function renderRecommendationState(data) {
  if (recommendationReadingId !== data?.analysis_id) recommendationError = '';
  recommendationReadingId = data?.analysis_id;
  if (questionnaireAnalysisId && questionnaireAnalysisId !== data?.analysis_id) resetQuestionnaire();
  if (!data) recommendationError = '';
  $('open-questionnaire').disabled = !data?.analysis_id || recommendationBusy;
  $('open-questionnaire').textContent = data?.orientation?.alcance === 'rostro_completo' ? 'Volver a evaluar' : 'Completar cuestionario';
  const state = data?.orientation?.estado;
  const evaluated = data?.orientation?.alcance === 'rostro_completo';
  $('detail-title').textContent = $('product-detail').hidden ? 'Lectura de tu piel' : evaluated ? 'Resultado de tus recomendaciones' : 'Recomendaciones para tu piel';
  const explanation = {
    SIN_RECOMENDACION_VALIDADA: 'El cuestionario se evaluó. Actualmente no hay productos aprobados y compatibles en el catálogo. Se necesita cargar y revisar las reglas antes de mostrar recomendaciones.',
    CATALOGO_NO_DISPONIBLE: 'El cuestionario se envió, pero no se pudo consultar el catálogo de productos.',
    DATOS_INCOMPLETOS: 'Hay respuestas desconocidas. Vuelve a evaluar para completarlas; si necesitas revisar alergias o tratamientos, consulta con un profesional.',
    REVISION_PROFESIONAL: 'El cuestionario se evaluó. Tus respuestas requieren revisión profesional antes de seleccionar productos.',
  };
  $('recommendation-context').hidden = !evaluated || !explanation[state];
  $('recommendation-context').textContent = evaluated ? explanation[state] || '' : '';
  const messages = data?.orientation?.mensajes;
  $('product-state').textContent = data ? (Array.isArray(messages) && messages.length ? messages.join(' ') : 'Completa el cuestionario para evaluar recomendaciones del catálogo.') : 'Primero analiza tu piel para habilitar el cuestionario.';
  if (data?.orientation?.alcance === 'rostro_completo') $('product-state').textContent += ' Evaluación del rostro completo.';
  $('recommendation-error').hidden = !recommendationError; $('recommendation-error').textContent = recommendationError;
}
$('open-questionnaire').onclick = () => {
  if (!snapshot?.diagnostic?.analysis_id || recommendationBusy) return;
  resetQuestionnaire(); recommendationError = '';
  questionnaireAnalysisId = snapshot.diagnostic.analysis_id;
  questionnaireDialog.showModal(); questionnaireForm.elements.sex.focus();
};
$('close-questionnaire').onclick = $('cancel-questionnaire').onclick = () => questionnaireDialog.close();
questionnaireDialog.addEventListener('close', resetQuestionnaire);
questionnaireForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (recommendationBusy || !questionnaireForm.reportValidity()) return;
  const id = questionnaireAnalysisId;
  if (!id || snapshot?.diagnostic?.analysis_id !== id) { resetQuestionnaire(); return; }
  const fields = new FormData(questionnaireForm), questionnaire = {age: Number(fields.get('age'))};
  for (const [name] of healthQuestions) {
    const inapplicable = fields.get('sex') === 'male' && ['is_pregnant', 'is_lactating'].includes(name);
    const answer = fields.get(name);
    questionnaire[name] = inapplicable ? false : !answer || answer === 'unknown' ? null : answer === 'yes';
  }
  for (const name of ['known_allergies', 'current_treatments']) {
    const choice = fields.get(`${name}_mode`);
    questionnaire[name] = choice === 'none' ? [] : null;
  }
  const currentGeneration = generation, attempt = ++recommendationAttempt;
  recommendationBusy = true; recommendationError = ''; $('questionnaire-error').hidden = true;
  $('submit-questionnaire').disabled = true; $('submit-questionnaire').textContent = 'Evaluando…'; render();
  try {
    const data = await (await request('recommendations', {analysis_id: id, questionnaire, scope: 'face', revision: snapshot.revision})).json();
    if (generation !== currentGeneration || attempt !== recommendationAttempt || snapshot?.diagnostic?.analysis_id !== id) return;
    snapshot.diagnostic = {...data, zone_preview_available: snapshot.diagnostic.zone_preview_available};
    questionnaireDialog.close(); details('product');
  } catch (error) {
    if (generation === currentGeneration && attempt === recommendationAttempt) {
      recommendationError = error.message;
      $('questionnaire-error').textContent = error.message; $('questionnaire-error').hidden = false;
    }
  } finally {
    if (attempt === recommendationAttempt) {
      recommendationBusy = false; $('submit-questionnaire').disabled = false; $('submit-questionnaire').textContent = 'Evaluar recomendaciones';
    }
    render();
  }
});

render(); pollFrame(); pollStatus();
