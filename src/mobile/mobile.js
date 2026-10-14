'use strict';
const $ = id => document.getElementById(id);
let token = '', snapshot = null, timer = null, busy = false, awaitingRevision = null;
let generation = 0, confirmationRevision = null, pendingSince = 0, connectionLost = false;
let polling = false, renderedDiagnostic = null, lastSync = null;
let questionnaireAnalysis = null;
let pendingPower = null; // 'shutdown'|'reboot'
let autoConnectAttempted = false;

const states = {
  BUSCANDO: ['Lista para escanear', 'Coloca el rostro dentro de la guía del equipo.'],
  ESTABILIZANDO: ['Preparando captura', 'Pide a la persona que mantenga el rostro quieto.'],
  ANALIZANDO: ['Analizando lectura', 'El resultado aparecerá aquí cuando el equipo termine.'],
  DIAGNOSTICADO: ['Lectura completada', 'El resultado de la lectura actual está disponible abajo.'],
  DESCONECTADO: ['Cámara no disponible', 'Comprueba que la cámara siga abierta en el equipo.']
};
const numberFormat = new Intl.NumberFormat('es-PE', {maximumFractionDigits: 2});
const clockFormat = new Intl.DateTimeFormat('es-PE', {hour: '2-digit', minute: '2-digit', second: '2-digit'});

function getPasswordFromUrl() {
  try {
    const params = new URLSearchParams(window.location.search);
    const p = params.get('password');
    if (p) return p.trim();
  } catch (e) {}
  return '';
}

function clearUrlParams() {
  try {
    const url = new URL(window.location);
    url.searchParams.delete('password');
    url.searchParams.delete('token');
    window.history.replaceState({}, document.title, url.pathname);
  } catch (e) {}
}

function number(value, suffix = '') {
  return typeof value === 'number' && Number.isFinite(value) ? numberFormat.format(value) + suffix : 'No disponible';
}
function message(text, error = false) {
  const target = $('dashboard').hidden ? $('pair-message') : $('message');
  target.textContent = text;
  target.classList.toggle('error', error);
}
async function request(path, options = {}) {
  const response = await fetch(path, {...options, cache: 'no-store',
    headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'},
    signal: AbortSignal.timeout(5000)});
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(typeof body.detail === 'string' ? body.detail : 'No se pudo completar la solicitud.');
    error.status = response.status;
    throw error;
  }
  return response.json();
}
async function pairWithPassword(password) {
  const response = await fetch('/api/pair', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({password}),
    cache: 'no-store',
    signal: AbortSignal.timeout(5000)
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(typeof body.detail === 'string' ? body.detail : 'Contraseña incorrecta.');
    error.status = response.status;
    throw error;
  }
  return response.json();
}
function clearDiagnostic() {
  $('diagnostic').hidden = true;
  renderedDiagnostic = null;
  questionnaireAnalysis = null;
  $('questionnaire-form').reset();
  for (const id of ['result-meta', 'spots', 'severity', 'age', 'phototype', 'phototype-label', 'indication', 'session-id', 'analysis-id', 'age-group', 'ita', 'glasses']) $(id).textContent = '';
  $('prescriptions').replaceChildren();
}
function element(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}
function renderDiagnostic(diagnostic) {
  if (!diagnostic || document.hidden) { clearDiagnostic(); return; }
  const key = JSON.stringify(diagnostic);
  if (key === renderedDiagnostic) return;
  renderedDiagnostic = key;
  if (questionnaireAnalysis !== diagnostic.analysis_id) {
    $('questionnaire-form').reset();
    $('questionnaire-message').textContent = '';
    questionnaireAnalysis = diagnostic.analysis_id;
  }
  $('orientation-message').textContent = (diagnostic.orientation?.mensajes || []).join(' ');
  const clinical = diagnostic.clinical || {};
  $('diagnostic').hidden = false;
  const date = new Date(diagnostic.reported_at);
  const dateText = Number.isNaN(date.getTime()) ? 'Hora no disponible' : date.toLocaleString('es-PE', {day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'});
  $('result-meta').textContent = `Lectura ${diagnostic.reading} · ${dateText}`;
  const local = typeof clinical.porcentaje_hiperpigmentacion_zona === 'number';
  const measured = local ? clinical.porcentaje_hiperpigmentacion_zona : clinical.porcentaje_hiperpigmentacion;
  $('measurement-title').textContent = local ? 'Tu zona señalada' : 'Área segmentada del rostro';
  $('measurement-unit').textContent = local ? 'del área seleccionada' : 'del área facial evaluada';
  $('measurement-note').textContent = local ? 'Porcentaje segmentado en la zona. Requiere interpretación profesional.' : 'Estimación del modelo para revisión profesional.';
  $('measurement-fill').style.width = `${Math.max(0, Math.min(100, measured || 0))}%`;
  $('global-context').hidden = !local;
  $('global-context').textContent = local ? `Rostro completo: ${number(clinical.porcentaje_hiperpigmentacion, ' %')} de área segmentada.` : '';
  $('questionnaire-card').hidden = local;
  $('spots').textContent = number(measured, ' %');
  $('spots').classList.toggle('unavailable', typeof clinical.porcentaje_hiperpigmentacion !== 'number');
  const level = clinical.clasificacion_severidad;
  $('severity').textContent = {NINGUNA: 'Ninguna', LEVE: 'Leve', MODERADA: 'Moderada', ALTA: 'Alta'}[level] || level || 'No disponible';
  $('severity').dataset.level = local ? '' : level || '';
  if (local) $('severity').textContent = 'Zona localizada';
  $('age').textContent = number(clinical.edad_biologica_estimada);
  $('age').classList.toggle('unavailable', typeof clinical.edad_biologica_estimada !== 'number');
  $('age-unit').hidden = typeof clinical.edad_biologica_estimada !== 'number';
  $('phototype').textContent = ['—', 'I', 'II', 'III', 'IV', 'V', 'VI'][clinical.fototipo_fitzpatrick] || '—';
  $('phototype-label').textContent = clinical.fototipo_label || 'No disponible';
  $('indication').textContent = clinical.indicacion_primaria || '';
  $('indication').hidden = !clinical.indicacion_primaria;
  $('session-id').textContent = diagnostic.session_id || 'No disponible';
  $('analysis-id').textContent = diagnostic.analysis_id || 'No disponible';
  $('age-group').textContent = {JOVEN: 'Joven', ADULTO: 'Adulto', MADURO: 'Maduro'}[clinical.estrato_etario] || clinical.estrato_etario || 'No disponible';
  $('ita').textContent = number(clinical.ita_deg, '°');
  $('glasses').textContent = clinical.gafas_detectadas === true ? 'Detectadas' : clinical.gafas_detectadas === false ? 'No detectadas' : 'No disponible';
  const prescriptions = diagnostic.prescriptions || [];
  $('no-prescriptions').hidden = prescriptions.length > 0;
  $('prescriptions').replaceChildren();
  for (const item of prescriptions) {
    const card = element('article', '', 'prescription');
    card.append(element('h4', item.nombre_comun || item.especie || 'Recomendación del equipo'));
    if (item.explicacion) card.append(element('p', item.explicacion));
    if (item.especie) card.append(element('p', item.especie, 'species'));
    const precaution = element('div', '', 'precaution');
    precaution.append(element('strong', 'Precauciones'), element('p', item.precauciones || 'El equipo no proporcionó precauciones para esta recomendación.'));
    card.append(precaution);
    if (item.fuentes?.length) card.append(element('p', `Fuentes: ${item.fuentes.join('; ')}`, 'hint'));
    $('prescriptions').append(card);
  }
}
function render() {
  const connected = snapshot?.connected;
  const state = connected ? snapshot.state : 'DESCONECTADO';
  const [title, description] = states[state] || states.DESCONECTADO;
  $('state').textContent = title;
  $('guidance').textContent = state === 'DIAGNOSTICADO' && !snapshot.diagnostic ? 'No hay un resultado disponible para mostrar. Puedes repetir la lectura.' : description;
  $('reading-count').textContent = `${snapshot?.samples ?? '—'} lecturas`;
  $('connection').textContent = connected ? '● Equipo conectado' : '○ Sin conexión con la cámara';
  $('sync').textContent = connected && lastSync ? `Actualizado ${clockFormat.format(lastSync)}` : 'Esperando conexión';
  $('dot').classList.toggle('offline', !connected);
  const touch = connected ? snapshot.touch : null;
  $('touch-instruction').textContent = touch?.message || 'Señala con el índice. Después, retira la mano.';
  $('scan-card').dataset.touch = touch?.state || '';
  if (touch?.message) $('guidance').textContent = touch.message;
  const pending = busy || snapshot?.pending || awaitingRevision !== null;
  $('restart').disabled = !connected || pending || state === 'ANALIZANDO';
  $('restart').textContent = pending ? 'Esperando al equipo…' : '↻ Reiniciar escaneo';
  const diagnostic = connected && !pending && state === 'DIAGNOSTICADO' ? snapshot.diagnostic : null;
  $('scan-card').classList.toggle('compact', Boolean(diagnostic));
  if (diagnostic && !$('message').classList.contains('error')) $('message').textContent = '';
  renderDiagnostic(diagnostic);
}
function disconnect() {
  generation++;
  clearTimeout(timer);
  token = ''; snapshot = null; busy = false; awaitingRevision = null; lastSync = null; connectionLost = false;
  $('confirm').returnValue = 'cancel'; $('confirm').close();
  $('password').value = ''; $('password').type = 'password';
  $('show-password').textContent = 'Ver'; $('show-password').setAttribute('aria-pressed', 'false'); $('show-password').setAttribute('aria-label', 'Mostrar contraseña');
  $('dashboard').hidden = true; $('pairing').hidden = false;
  $('connect').disabled = false;
  $('message').textContent = ''; $('pair-message').textContent = '';
  document.body.classList.remove('connected');
  $('page-title').textContent = 'Tu piel, de cerca.';
  $('intro').textContent = 'Señala una zona de tu rostro frente al espejo. Revisa aquí la lectura de tu piel.';
  clearDiagnostic();
}
async function poll() {
  clearTimeout(timer);
  if (!token || document.hidden || polling) return;
  polling = true; $('refresh').disabled = true;
  const currentGeneration = generation;
  try {
    const result = await request('/api/status');
    if (currentGeneration !== generation || document.hidden) return;
    snapshot = result; lastSync = new Date();
    if (connectionLost) { message('Conexión recuperada.'); connectionLost = false; }
    if (awaitingRevision !== null && result.applied_revision === awaitingRevision) {
      awaitingRevision = null;
      message('Escaneo reiniciado. Esperando una nueva lectura.');
    } else if (awaitingRevision !== null && result.revision > awaitingRevision) {
      awaitingRevision = null;
      message('El escaneo cambió desde el equipo. Revisa su estado antes de repetir la lectura.', true);
    } else if (awaitingRevision !== null && Date.now() - pendingSince > 12000 && !result.pending) {
      awaitingRevision = null;
      message('El equipo no confirmó el reinicio. Revisa la cámara antes de intentarlo de nuevo.', true);
    }
    render();
  } catch (error) {
    if (currentGeneration !== generation) return;
    if (error.status === 401) { disconnect(); message(error.message, true); return; }
    connectionLost = true; snapshot = null; render();
    message('Se perdió la conexión. El resultado se ocultó hasta volver a conectar.', true);
  } finally {
    polling = false; $('refresh').disabled = false;
    if (token && !document.hidden) timer = setTimeout(poll, 1500);
  }
}
async function doLoginWithPassword(password) {
  const { token: t } = await pairWithPassword(password);
  token = t;
  const result = await request('/api/status');
  snapshot = result; lastSync = new Date();
  $('password').value = '';
  clearUrlParams();
  try { localStorage.setItem(`derma_token_${location.host}`, token); } catch (e) {}
  $('pairing').hidden = true; $('dashboard').hidden = false;
  $('pair-message').textContent = '';
  document.body.classList.add('connected');
  $('page-title').textContent = 'Tu espejo, conectado';
  $('intro').textContent = 'Señala, retira la mano y descubre la lectura de esa zona.';
  message('Equipo vinculado. Los resultados se actualizan automáticamente.');
  render(); poll();
}
window.addEventListener('DOMContentLoaded', async () => {
  const urlPass = getPasswordFromUrl();
  const qrImg = $('qr-image');
  if (qrImg) qrImg.src = `/pairing/qr.png?ts=${Date.now()}`;
  if (urlPass && !autoConnectAttempted) {
    autoConnectAttempted = true;
    busy = true; $('connect').disabled = true;
    const currentGeneration = generation;
    try {
      await doLoginWithPassword(urlPass);
      return;
    } catch (error) {
      clearUrlParams();
      token = '';
      message(error.status ? error.message : 'Contraseña incorrecta. Inténtalo de nuevo.', true);
    } finally {
      busy = false; $('connect').disabled = false;
    }
  } else {
    try {
      const saved = localStorage.getItem(`derma_token_${location.host}`);
      if (saved) token = saved;
    } catch (e) {}
  }
});
$('pair-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (busy) return;
  busy = true; $('connect').disabled = true;
  const pass = $('password').value.trim();
  const currentGeneration = generation;
  try {
    await doLoginWithPassword(pass);
  } catch (error) {
    token = ''; message(error.status ? error.message : 'Contraseña incorrecta. Inténtalo de nuevo.', true);
  } finally { busy = false; $('connect').disabled = false; }
});
$('show-password').addEventListener('click', () => {
  const visible = $('password').type === 'password';
  $('password').type = visible ? 'text' : 'password';
  $('show-password').textContent = visible ? 'Ocultar' : 'Ver';
  $('show-password').setAttribute('aria-label', visible ? 'Ocultar contraseña' : 'Mostrar contraseña');
  $('show-password').setAttribute('aria-pressed', String(visible));
});
$('logout').addEventListener('click', () => {
  try { localStorage.removeItem(`derma_token_${location.host}`); } catch (e) {}
  disconnect();
  message('Consulta cerrada. Los resultados se retiraron de esta pantalla.');
});
$('refresh').addEventListener('click', poll);
$('restart').addEventListener('click', () => {
  confirmationRevision = snapshot?.revision;
  $('confirm').returnValue = 'cancel'; $('confirm').showModal();
});
$('confirm').addEventListener('close', async () => {
  if ($('confirm').returnValue !== 'restart' || busy || !snapshot?.connected) return;
  busy = true; awaitingRevision = confirmationRevision; pendingSince = Date.now(); render();
  const currentGeneration = generation;
  try {
    await request('/api/restart', {method: 'POST', body: JSON.stringify({revision: confirmationRevision})});
    if (currentGeneration !== generation) return;
    message('Solicitud enviada. Esperando confirmación de la cámara…');
  } catch (error) {
    if (currentGeneration !== generation) return;
    if (error.status) awaitingRevision = null;
    message(error.status ? error.message : 'No se recibió respuesta. Consultando si el equipo aplicó el reinicio…', true);
  } finally {
    if (currentGeneration === generation) { busy = false; render(); }
  }
});
$('reboot-btn').addEventListener('click', () => {
  pendingPower = 'reboot';
  $('confirm-power-title').textContent = '¿Reiniciar la Raspberry Pi?';
  $('confirm-power-text').textContent = 'El equipo se reiniciará. La conexión se perderá durante unos segundos y volverá a establecerse cuando arranque.';
  $('confirm-power-action').textContent = 'Sí, reiniciar equipo';
  $('confirm-power-action').className = 'secondary';
  $('confirm-power').showModal();
});
$('shutdown-btn').addEventListener('click', () => {
  pendingPower = 'shutdown';
  $('confirm-power-title').textContent = '¿Apagar la Raspberry Pi?';
  $('confirm-power-text').textContent = 'El equipo se apagará por completo. Para volver a encenderlo necesitarás alimentarlo físicamente.';
  $('confirm-power-action').textContent = 'Sí, apagar equipo';
  $('confirm-power-action').className = 'danger';
  $('confirm-power').showModal();
});
$('confirm-power').addEventListener('close', async () => {
  if ($('confirm-power').returnValue !== 'confirm' || !pendingPower || busy) {
    pendingPower = null;
    return;
  }
  busy = true;
  render();
  const path = pendingPower === 'shutdown' ? '/api/system/shutdown' : '/api/system/reboot';
  const currentGeneration = generation;
  try {
    await request(path, {method: 'POST', body: JSON.stringify({confirm: true})});
    if (currentGeneration !== generation) return;
    message(`Solicitud de ${pendingPower === 'shutdown' ? 'apagado' : 'reinicio'} enviada. El equipo se desconectará en breve.`);
    setTimeout(disconnect, 1500);
  } catch (error) {
    if (currentGeneration !== generation) return;
    message(error.status ? error.message : 'No se pudo ejecutar la acción del sistema.', true);
  } finally {
    pendingPower = null;
    busy = false;
    render();
  }
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    generation++; clearTimeout(timer); snapshot = null; render();
    if ($('dashboard').hidden) disconnect();
  }
  else if (token) poll();
});
window.addEventListener('pagehide', disconnect);

const questionnaireFlags = {
  sensitive_skin: '¿Tiene piel sensible?',
  salicylate_allergy: '¿Tiene alergia a salicilatos?',
  is_pregnant: '¿Está embarazada?',
  is_lactating: '¿Está en periodo de lactancia?',
  has_open_wounds: '¿Tiene heridas abiertas en la zona?',
  has_cystic_acne: '¿Tiene acné quístico diagnosticado?',
  concerning_changes: '¿Hay lesiones que cambian, sangran o preocupan a la persona?'
};
for (const [name, title] of Object.entries(questionnaireFlags)) {
  const label = element('label', title);
  const select = document.createElement('select');
  select.name = name;
  select.required = true;
  for (const [value, text] of [['', 'Selecciona una respuesta'], ['false', 'No / No aplica'], ['true', 'Sí']]) {
    const option = element('option', text);
    option.value = value;
    select.append(option);
  }
  label.append(select);
  $('questionnaire-flags').append(label);
}
$('questionnaire-form').addEventListener('submit', async event => {
  event.preventDefault();
  const analysisId = questionnaireAnalysis;
  if (!analysisId) return;
  const form = event.currentTarget;
  const fields = new FormData(form);
  const questionnaire = {age: Number(fields.get('age'))};
  for (const name of Object.keys(questionnaireFlags)) questionnaire[name] = fields.get(name) === 'true';
  for (const name of ['known_allergies', 'current_treatments']) {
    questionnaire[name] = fields.get(name).split(',').map(value => value.trim()).filter(Boolean);
  }
  const button = form.querySelector('button');
  button.disabled = true;
  try {
    const diagnostic = await request('/api/recommendations', {method: 'POST', body: JSON.stringify({analysis_id: analysisId, questionnaire})});
    if (questionnaireAnalysis !== analysisId) return;
    snapshot.diagnostic = diagnostic;
    renderDiagnostic(diagnostic);
    form.reset();
    $('questionnaire-message').textContent = 'Evaluación completada. Revisa el resultado debajo.';
  } catch (error) {
    if (questionnaireAnalysis === analysisId) $('questionnaire-message').textContent = error.message;
  } finally { button.disabled = false; }
});
