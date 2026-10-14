"""Proyección explícita del resultado existente; no calcula reglas clínicas."""
import math
from datetime import datetime, timezone
from numbers import Real

TEXT_FIELDS = ('clasificacion_severidad', 'fototipo_label', 'estrato_etario', 'indicacion_primaria')
NUMBER_FIELDS = ('edad_biologica_estimada', 'porcentaje_hiperpigmentacion', 'fototipo_fitzpatrick', 'ita_deg', 'porcentaje_hiperpigmentacion_zona')
PRESCRIPTION_FIELDS = ('condicion_objetivo', 'especie', 'nombre_comun', 'precauciones', 'explicacion')


def project_appearance(appearance):
    """Lista blanca: solo señales numéricas de la lectura, nunca imágenes."""
    if not isinstance(appearance, dict) or appearance.get('method') != 'visual-appearance-v1':
        return None
    status = appearance.get('status')
    if status not in ('EXPERIMENTAL', 'SELECCIONA_ZONA', 'SIN_DETALLE', 'LUZ_INADECUADA', 'ZONA_INVALIDA'):
        return None
    clean = {'status': status, 'method': 'visual-appearance-v1', 'scope': 'selected_region',
             'unit': 'visible_area_percent'}
    for key in ('shine', 'texture', 'dryness_cues'):
        value = appearance.get(key)
        clean[key] = float(value) if (status == 'EXPERIMENTAL' and isinstance(value, Real)
            and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 100) else None
    return clean


def project_diagnostic(result, session_id, samples):
    if not isinstance(result, dict) or 'error' in result:
        return None
    data = result.get('datos')
    if not isinstance(data, dict) or not isinstance(data.get('clinica'), dict):
        return None
    clinical = data['clinica']
    clean = {key: clinical[key] for key in TEXT_FIELDS if isinstance(clinical.get(key), str)}
    for key in NUMBER_FIELDS:
        value = clinical.get(key)
        if isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value):
            clean[key] = float(value)
    if isinstance(clinical.get('gafas_detectadas'), bool):
        clean['gafas_detectadas'] = clinical['gafas_detectadas']
    region = clinical.get('zona_seleccionada')
    if isinstance(region, dict) and all(isinstance(region.get(k), Real) and math.isfinite(region[k]) for k in ('x', 'y', 'radius')):
        clean['zona_seleccionada'] = {k: float(region[k]) for k in ('x', 'y', 'radius')}
    prescriptions = data.get('prescripciones')
    prescriptions = prescriptions if isinstance(prescriptions, list) else []
    quality = data.get('capture_quality')
    quality = quality if isinstance(quality, dict) else {}
    clean_quality = {key: value for key, value in quality.items()
                     if key in ('luminance', 'clipped_percent') and isinstance(value, Real)
                     and not isinstance(value, bool) and math.isfinite(value)}
    if quality.get('status') in ('ACEPTABLE',):
        clean_quality['status'] = quality['status']
    return {
        'session_id': str(session_id or ''),
        'analysis_id': data.get('sesion_id') if isinstance(data.get('sesion_id'), str) else None,
        'reading': samples,
        'reported_at': datetime.now(timezone.utc).isoformat(),
        'clinical': clean,
        'capture_quality': clean_quality,
        'visual_appearance': project_appearance(data.get('visual_appearance')),
        'orientation': data.get('orientacion', {}),
        'prescriptions': [
            {**{key: item[key] for key in PRESCRIPTION_FIELDS if isinstance(item.get(key), str)},
             "fuentes": [source for source in item.get("fuentes", []) if isinstance(source, str)]
             if isinstance(item.get("fuentes"), list) else []}
            for item in prescriptions if isinstance(item, dict)
        ],
    }
