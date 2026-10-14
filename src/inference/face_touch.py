"""Selección por señalamiento 2D del índice; no certifica contacto físico ni profundidad."""
from dataclasses import dataclass
import cv2
import numpy as np

# Regiones excluidas: párpados y labios. Coordenadas MediaPipe Face Landmarker.
EXCLUDED = ((33, 160, 158, 133, 153, 144), (362, 385, 387, 263, 373, 380),
            (61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91))


def skin_point(face, point):
    face = np.asarray(face, dtype=np.float32)
    if face.shape[0] < 468 or not np.isfinite(face).all():
        return False
    width = float(np.ptp(face[:, 0]))
    margin = max(2.0, width * .075)
    p = tuple(map(float, point))
    if cv2.pointPolygonTest(cv2.convexHull(face[:468, :2]), p, True) < margin:
        return False
    return not any(cv2.pointPolygonTest(cv2.convexHull(face[list(ids), :2]), p, True) >= -margin for ids in EXCLUDED)


def index_tip(hand):
    """Índice extendido; se descartan puños y geometrías degeneradas."""
    h = np.asarray(hand, dtype=float)
    if h.shape != (21, 2) or not np.isfinite(h).all():
        return None
    palm = np.linalg.norm(h[0] - h[9])
    if palm < 4:
        return None
    if np.linalg.norm(h[8] - h[5]) < 1.15 * np.linalg.norm(h[6] - h[5]):
        return None
    if np.linalg.norm(h[8] - h[0]) <= np.linalg.norm(h[6] - h[0]):
        return None
    return h[8]


@dataclass
class FaceAnchor:
    indices: tuple
    weights: np.ndarray

    @classmethod
    def at(cls, face, point):
        """Coordenadas baricéntricas locales: la zona acompaña al rostro al moverse."""
        face = np.asarray(face, dtype=float)[:468, :2]
        near = np.argsort(np.linalg.norm(face - point, axis=1))[:18]
        for i in range(len(near) - 2):
            for j in range(i + 1, len(near) - 1):
                for k in range(j + 1, len(near)):
                    ids = (int(near[i]), int(near[j]), int(near[k]))
                    matrix = np.vstack((face[list(ids)].T, np.ones(3)))
                    if abs(np.linalg.det(matrix)) < 2:
                        continue
                    weights = np.linalg.solve(matrix, [*point, 1])
                    if np.all(weights >= -.03) and np.all(weights <= 1.03):
                        return cls(ids, weights)
        return None

    def point(self, face):
        return self.weights @ np.asarray(face)[list(self.indices), :2]


class FaceTouchSelector:
    def __init__(self, hold_seconds=.45, clear_seconds=.35, stable_seconds=1.5):
        self.hold_seconds = hold_seconds
        self.clear_seconds = clear_seconds
        self.stable_seconds = stable_seconds
        self.reset()

    def reset(self):
        self.anchor = None
        self.candidate = None
        self.since = None
        self.clear_since = None
        self.stable_since = None
        self.previous_center = None
        self.selected_at = None
        self.last_time = None
        self.state = 'ESPERANDO_ZONA'
        self.progress = 0.0
        self.point = None
        self.radius = 0.0

    @property
    def message(self):
        return {
            'ESPERANDO_ZONA': 'Señala una zona de tu rostro con el índice',
            'FIJANDO_ZONA': 'Mantén el dedo en esa zona un momento',
            'RETIRA_MANO': 'Zona seleccionada. Retira la mano del rostro',
            'ESTABILIZANDO': 'Mantén el rostro quieto para medir la zona',
            'LISTO': 'Zona lista para analizar',
        }[self.state]

    def update(self, face, hands, now):
        # No reutilizar selecciones tras perder el rostro o pausar la captura.
        if face is None or len(face) < 468:
            self.reset()
            return False
        if self.last_time is not None and (now - self.last_time > .75 or now < self.last_time):
            self.reset()
        self.last_time = now
        face = np.asarray(face, dtype=float)[:, :2]
        width = float(np.ptp(face[:, 0]))
        if width < 60 or not np.isfinite(face).all():
            self.reset()
            return False
        self.radius = width * .075
        hull = cv2.convexHull(face[:468].astype(np.float32))
        # Cualquier parte de una mano dentro/cerca del rostro bloquea la medición.
        occluded = any(any(cv2.pointPolygonTest(hull, tuple(map(float, p)), True) >= -width * .08
                           for p in hand) for hand in hands)
        if self.anchor is None:
            tips = [tip for hand in hands if (tip := index_tip(hand)) is not None and skin_point(face, tip)]
            if len(tips) != 1:
                self.candidate = self.since = self.point = None
                self.state = 'ESPERANDO_ZONA'
                self.progress = 0.0
                return False
            tip = tips[0]
            if self.candidate is None or np.linalg.norm(tip - self.candidate) > width * .05:
                self.since, self.candidate = now, tip.copy()
            self.point = tip.copy()
            self.state = 'FIJANDO_ZONA'
            self.progress = min(1.0, (now - self.since) / self.hold_seconds)
            if self.progress >= 1:
                self.anchor = FaceAnchor.at(face, tip)
                if self.anchor is not None:
                    self.selected_at = now
                    self.state = 'RETIRA_MANO'
            return False
        self.point = self.anchor.point(face)
        if now - self.selected_at > 12 or not skin_point(face, self.point):
            self.reset()
            return False
        if occluded:
            self.state = 'RETIRA_MANO'
            self.clear_since = self.stable_since = self.previous_center = None
            self.progress = 0.0
            return False
        if self.clear_since is None:
            self.clear_since = now
        if now - self.clear_since < self.clear_seconds:
            return False
        center = face[4]
        if self.previous_center is None or np.linalg.norm(center - self.previous_center) > width * .025:
            self.stable_since = now
        self.previous_center = center.copy()
        self.state = 'ESTABILIZANDO'
        self.progress = min(1.0, (now - self.stable_since) / self.stable_seconds)
        if self.progress >= 1:
            self.state = 'LISTO'
            return True
        return False

    def region_in_roi(self, face, box):
        x, y, width, height = box
        point = self.anchor.point(face)
        return {'x': float((point[0] - x) / width), 'y': float((point[1] - y) / height),
                'radius': float(self.radius / min(width, height))}
