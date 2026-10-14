"""HUD de espejo botánico: aro cálido, señalamiento y mediciones reales."""
import cv2
import numpy as np
import unicodedata

GOLD = (133, 193, 223)
CREAM = (211, 233, 243)
MUTED = (170, 192, 197)
OLIVE = (27, 43, 37)


def text(frame, value, position, size=.55, color=CREAM):
    # Hershey no soporta acentos: usar etiquetas legibles sin glifos rotos.
    value = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode()
    cv2.putText(frame, value, position, cv2.FONT_HERSHEY_SIMPLEX, size, color, 1, cv2.LINE_AA)


def draw_mirror_hud(frame, selector, result, state, error=''):
    h, w = frame.shape[:2]
    scale = min(w / 1280, h / 720)
    cx, cy = int(w * .39), int(h * .49)
    axes = (int(w * .28), int(h * .43))
    # Atenuar solo el exterior del espejo; mantener píxeles originales dentro.
    mask = np.zeros((h, w), np.uint8)
    cv2.ellipse(mask, (cx, cy), axes, 0, 0, 360, 255, -1)
    dark = np.empty_like(frame)
    dark[:] = OLIVE
    tinted = cv2.addWeighted(frame, .35, dark, .65, 0)
    frame[mask == 0] = tinted[mask == 0]
    cv2.ellipse(frame, (cx, cy), axes, 0, 0, 360, (65, 100, 116), max(3, int(9*scale)), cv2.LINE_AA)
    cv2.ellipse(frame, (cx, cy), axes, 0, 0, 360, GOLD, max(2, int(4*scale)), cv2.LINE_AA)
    cv2.ellipse(frame, (cx, cy), axes, 0, 0, 360, CREAM, 1, cv2.LINE_AA)
    text(frame, 'D E R M A', (int(w*.33), int(h*.11)), .65*scale)
    if selector.point is not None:
        p = tuple(np.round(selector.point).astype(int))
        radius = max(10, int(selector.radius))
        cv2.circle(frame, p, radius, CREAM, 1, cv2.LINE_AA)
        cv2.circle(frame, p, radius+5, GOLD, 1, cv2.LINE_AA)
        cv2.ellipse(frame, p, (radius+8, radius+8), -90, 0, selector.progress*360, GOLD, 2, cv2.LINE_AA)
    x, y = int(w*.70), int(h*.23)
    text(frame, 'Tu piel, de cerca', (x, y), .66*scale)
    text(frame, 'Zona senalada', (x, y+int(38*scale)), .44*scale, MUTED)
    cv2.line(frame, (x, y+int(58*scale)), (w-25, y+int(58*scale)), GOLD, 1)
    data = (result or {}).get('datos', {})
    clinical = data.get('clinica', {})
    value = clinical.get('porcentaje_hiperpigmentacion_zona')
    text(frame, f'{value:.2f} %' if value is not None else '--', (x, y+int(110*scale)), 1.1*scale)
    text(frame, 'Area segmentada en la zona', (x, y+int(142*scale)), .40*scale, MUTED)
    text(frame, 'Revision profesional', (x, y+int(222*scale)), .52*scale)
    text(frame, 'Consulta el detalle en tu celular', (x, y+int(255*scale)), .39*scale, MUTED)
    if value is None:
        text(frame, 'Esperando una medicion', (x, y+int(174*scale)), .40*scale, MUTED)
    msg = error or ('Zona evaluada. Pulsa R para elegir otra.' if state == 'DIAGNOSTICADO' else selector.message)
    if state == 'ANALIZANDO':
        msg = 'Analizando la zona seleccionada...'
    overlay = frame.copy()
    cv2.rectangle(overlay, (int(w*.08), h-70), (int(w*.92), h-16), OLIVE, -1)
    cv2.addWeighted(overlay, .85, frame, .15, 0, dst=frame)
    text(frame, msg, (int(w*.10), h-37), .50*scale)
