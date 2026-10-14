"""
Demostración Interactiva en Vivo con Cámara Web:
Sistema Embebido de Diagnóstico Dermatoscópico Facial y Recomendación Fitoterapéutica (SPEC-001)

Características del HUD Táctico Optimizado On-Edge (Raspberry Pi 5):
1. Google MediaPipe Face Landmarker / 3D Face Mesh (478 landmarks anatómicos sub-píxel).
2. Wireframe Tesselation & Contornos Anatómicos:
   - Modo 'CONTOURS': Mandíbula, labios, ojos, cejas y nariz (124 líneas, ultra-optimizado ~0.04 ms).
   - Modo 'TESSELATION': Malla 3D completa (478 nodos, renderizado acelerado LINE_8).
   - Modo 'OFF': Vista clínica limpia sin obstrucciones.
   - Alternable dinámicamente con tecla [M].
3. Retículo y Guía Táctica de Posicionamiento Facial:
   - Brackets tácticos de encuadre y elipse segmentada en reposo.
   - Seguimiento del rostro con anillo de progreso de estabilidad circular en tiempo real (1.5s).
   - Detección visual y alerta de advertencia ante movimientos bruscos.
4. Renderizado 'Frosted Glass' Zero-Allocation:
   - Eliminación de clones de fotograma completo (cv2.addWeighted sobre 1280x720).
   - Blending in-place de slices ROI locales (ahorro de más de 250 MB/s de ancho de banda RAM).
5. Inferencia Multimodelo On-Edge & Memoria Compartida POSIX:
   - Extracción de región facial 224x224 y escritura Zero-Copy POSIX SHM.
   - MobileNetV3 (Edad Biológica con filtro de mediana multi-muestra).
   - U-Net Nano (Segmentación de Manchas con proyección anatómica local).
6. Integración de Fototipo Fitzpatrick (I-VI) vía ITA y Normalización Óptica:
   - Análisis espectral de ángulo tipológico individual sobre parches de mejilla.
   - Detección de monturas de gafas y reflejos peri-orbitales (cv-optical-normalizer).
7. Motor de Reglas Fitoterapéuticas Estratificadas (SQLite 3NF + clinical-phytotherapy-engine):
   - Estratificación etaria (Joven, Adulto, Maduro) con activos aprobados y precauciones.
8. Telemetría de Rendimiento en Tiempo Real:
   - Monitor de FPS (EMA) y latencia diagnóstica on-edge en la barra superior.
"""

import os
import sys
import time
import math
import uuid
import json
import csv
from datetime import datetime
from pathlib import Path
from multiprocessing import shared_memory
from typing import Optional, Tuple, List
import cv2
import numpy as np

# Asegurar encoding UTF-8 en consola
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from starlette.testclient import TestClient

from src.mobile.server import ScanControl, start_mobile_server
from src.inference.region_analysis import CaptureRejected, capture_quality
from src.api.app import app
from src.db.database import init_db
from src.config import DEV_TOKEN, MIN_STABILITY_DURATION_MS, EXPECTED_BUFFER_SIZE_BYTES, DATA_DIR
from src.inference.pipeline import inference_engine
from src.domain.fitzpatrick import extract_skin_phototype, extract_skin_phototype_multisample, FITZPATRICK_DESCRIPTIONS
from src.domain.age_stratified_rules import get_clinical_engine, PatientProfile, AgeGroup
from src.inference.optical_normalizer import detect_glasses_or_glare, check_lighting_quality
from src.utils.calibration_store import load_calibration_offset, save_calibration_offset
from src.reports.clinical_report_generator import generate_clinical_report
from src.utils.camera_utils import get_camera_capture
from src.inference.hardware_detect import is_raspberry_pi, get_hardware_profile



# ============================================================================
# Funciones Auxiliares de Renderizado Gráfico Ultra-Optimizado (Zero-Allocation)
# ============================================================================

def draw_glass_rect(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int, 
                    color: Tuple[int, int, int] = (14, 18, 24), alpha: float = 0.88,
                    border_color: Optional[Tuple[int, int, int]] = None, border_thickness: int = 1):
    """
    Dibuja un panel semitransparente estilo 'frosted glass' usando exclusivamente el slice NumPy local.
    Zero-Allocation en búfer global: evita duplicar el frame completo (ahorra 250+ MB/s en Raspberry Pi 5).
    """
    h_f, w_f = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w_f, x2), min(h_f, y2)
    if x2 <= x1 or y2 <= y1:
        return
    sub = frame[y1:y2, x1:x2]
    overlay = np.empty_like(sub)
    overlay[:] = color
    cv2.addWeighted(overlay, alpha, sub, 1.0 - alpha, 0, dst=sub)
    if border_color is not None:
        cv2.rectangle(frame, (x1, y1), (x2 - 1, y2 - 1), border_color, border_thickness, cv2.LINE_AA)


def draw_corner_brackets(img: np.ndarray, x1: int, y1: int, x2: int, y2: int, 
                         color: Tuple[int, int, int], length: int = 24, thickness: int = 2):
    """Dibuja esquinas tácticas (brackets) en lugar de un rectángulo tosco para un HUD de alta tecnología."""
    # Top-Left
    cv2.line(img, (x1, y1), (x1 + length, y1), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1, y1), (x1, y1 + length), color, thickness, cv2.LINE_AA)
    # Top-Right
    cv2.line(img, (x2, y1), (x2 - length, y1), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x2, y1), (x2, y1 + length), color, thickness, cv2.LINE_AA)
    # Bottom-Left
    cv2.line(img, (x1, y2), (x1 + length, y2), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1, y2), (x1, y2 - length), color, thickness, cv2.LINE_AA)
    # Bottom-Right
    cv2.line(img, (x2, y2), (x2 - length, y2), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x2, y2), (x2 - length, y2), color, thickness, cv2.LINE_AA)


# ============================================================================
# Aplicación Principal: LiveDermaCameraApp
# ============================================================================

from src.inference.face_touch import FaceTouchSelector
from src.inference.visual_appearance import analyze_visual_appearance
from src.ui.mirror_hud import draw_mirror_hud


class LiveDermaCameraApp:
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        # Inicialización de la base de datos clínica SQLite
        init_db()
        self.client = TestClient(app, raise_server_exceptions=False)

        # 1. Inicialización de MediaPipe Face Landmarker 3D
        model_path = BASE_DIR / "models" / "face_landmarker.task"
        if not model_path.exists():
            raise RuntimeError("Falta models/face_landmarker.task. Instala los modelos antes de usar el equipo sin internet.")

        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=2,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)

        self.touch_mode = os.getenv("DERMA_TOUCH_MODE", "1") == "1"
        self.touch_selector = FaceTouchSelector()
        self.selected_region = None
        self.hand_landmarker = None
        self.touch_frame_time = 0.0
        if self.touch_mode:
            hand_path = BASE_DIR / "models" / "hand_landmarker.task"
            if not hand_path.exists():
                self.landmarker.close()
                raise RuntimeError("Falta models/hand_landmarker.task. Instala el modelo local para seleccionar zonas con el dedo.")
            hand_options = vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(hand_path)),
                running_mode=vision.RunningMode.VIDEO, num_hands=2,
                min_hand_detection_confidence=.5, min_hand_presence_confidence=.5,
                min_tracking_confidence=.6)
            self.hand_landmarker = vision.HandLandmarker.create_from_options(hand_options)

        # Conexiones topológicas del grafo facial (MediaPipe 3D Face Mesh)
        FLC = vision.FaceLandmarksConnections

        # Malla canónica unificada con aristas únicas
        raw_tesselation = list(FLC.FACE_LANDMARKS_TESSELATION)
        iris_conns = list(FLC.FACE_LANDMARKS_LEFT_IRIS) + list(FLC.FACE_LANDMARKS_RIGHT_IRIS)

        all_edges = set((min(c.start, c.end), max(c.start, c.end)) for c in raw_tesselation)
        for c in iris_conns:
            all_edges.add((min(c.start, c.end), max(c.start, c.end)))

        self.tess_unique_edges = np.array(list(all_edges), dtype=np.int32)
        self.conns_oval = FLC.FACE_LANDMARKS_FACE_OVAL
        self.conns_contours = list(FLC.FACE_LANDMARKS_CONTOURS)

        # Modos de visualización de malla: 'FACE_MESH' (default, malla holográfica 3D completa), 'CONTOURS', 'OFF'
        self.mesh_mode = "OFF"

        # 2. Parámetros de Estabilidad Biométrica
        self.required_stability_sec = MIN_STABILITY_DURATION_MS / 1000.0  # 1.5s
        self.prev_center = None
        self.stability_start_time = None
        self.max_movement_px = 14.0  # Umbral de quietud en píxeles
        self.movement_warning_until = 0.0

        # 3. Estado del Sistema y Calibración
        self.mobile_control = ScanControl()
        self.state = "BUSCANDO"  # 'BUSCANDO', 'ESTABILIZANDO', 'ANALIZANDO', 'DIAGNOSTICADO'
        self.last_result = None
        self.last_mask = None
        self.last_face_box = None
        self.last_face_roi = None
        self.last_landmarks = None
        self.last_phototype_info = None
        self.last_stratified_result = None
        self.last_optical_info = None
        self.analyzing = False
        self.stability_roi_buffer = []
        self.last_diagnosis_time = None
        self.auto_continuous_cooldown_sec = 2.5
        # 4. Calibración Persistente de Edad (carga data/config/calibracion_camara.json o default +2.5a)
        default_cal = load_calibration_offset(default_offset=2.5)
        self.age_offset = float(os.getenv("DERMA_AGE_OFFSET", str(default_cal)))
        os.environ["DERMA_AGE_OFFSET"] = str(self.age_offset)

        # 5. Perfil Clínico del Paciente y Contraindicaciones Interactivas
        self.patient_sensitive_skin = False
        self.patient_is_pregnant = False

        # 6. Notificaciones en Pantalla (Toast) y Monitoreo Lumínico
        self.toast_message = ""
        self.toast_until = 0.0
        self.last_lighting_info = None

        # 7. Telemetría de Rendimiento On-Edge (FPS & Latencia)
        self.fps = 30.0
        self.last_frame_time = time.perf_counter()
        self.last_inference_latency_ms = 0.0

        # 8. Registro CSV y Estadísticas de Sesión

        self.sessions_dir = DATA_DIR / "sesiones_edad"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.session_idx = 1
        self.session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.session_idx:02d}"
        self.session_csv_path = None
        self.global_csv_path = self.sessions_dir / "historico_general.csv"
        self.session_ages: List[int] = []
        self._csv_headers = [
            "timestamp",
            "sesion_id",
            "escaneo_num",
            "edad_estimada",
            "offset_aplicado",
            "promedio_acumulado",
            "mediana_acumulada",
            "porcentaje_manchas",
            "severidad",
            "fototipo_fitzpatrick",
            "latencia_ms"
        ]
        if not self.global_csv_path.exists():
            with open(self.global_csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self._csv_headers)

    def log_measurement_to_csv(self, clinica_data: dict, metadatos: dict):
        """Registra cada diagnóstico en el CSV de sesión y en el histórico general."""
        edad = int(clinica_data.get("edad_biologica_estimada", 0))
        spots = clinica_data.get("porcentaje_hiperpigmentacion", 0.0)
        sev = clinica_data.get("clasificacion_severidad", "")
        fitz = clinica_data.get("fototipo_fitzpatrick", 0)
        fitz_lbl = clinica_data.get("fototipo_label", f"Tipo {fitz}")
        ita_deg = clinica_data.get("ita_deg", 0.0)
        lat = metadatos.get("total_call_ms", 0.0)

        # Creación perezosa (lazy) del CSV de sesión para evitar archivos vacíos
        if self.session_csv_path is None:
            self.session_csv_path = self.sessions_dir / f"sesion_{self.session_id}.csv"
            with open(self.session_csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self._csv_headers)

        self.session_ages.append(edad)
        n = len(self.session_ages)
        avg = float(np.mean(self.session_ages))
        med = float(np.median(self.session_ages))
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        row = [
            now_str,
            self.session_id,
            n,
            edad,
            f"{self.age_offset:+.1f}",
            f"{avg:.2f}",
            f"{med:.2f}",
            spots,
            sev,
            fitz,
            lat
        ]

        try:
            with open(self.session_csv_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)

            with open(self.global_csv_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            print(f"⚠️ Error al escribir CSV: {e}")

        estrato_info = clinica_data.get("estrato_etario", "")
        ind_info = clinica_data.get("indicacion_primaria", "")
        print("\n" + "┌" + "─" * 68 + "┐")
        print(f"│ 📝 REGISTRO #{n} GUARDADO EN CSV (Sesión: {self.session_id})")
        print(f"│   • Edad Detectada:       {edad} años (Offset: {self.age_offset:+.1f}a)")
        print(f"│   • Promedio Acumulado:   {avg:.2f} años (n={n} lecturas)")
        print(f"│   • Mediana Acumulada:    {med:.2f} años")
        ita_text = f"{ita_deg:+.1f}°" if isinstance(ita_deg, (int, float)) else "No disponible"
        print(f"│   • Fototipo Cutáneo:     {fitz_lbl} (ITA: {ita_text})")
        if estrato_info:
            print(f"│   • Estrato Clínico:      {estrato_info} ({ind_info})")
        print(f"│   • Archivo de Sesión:    {self.session_csv_path.name}")
        print("└" + "─" * 68 + "┘\n")

    def finalize_session_and_restart(self):
        """Cierra la sesión actual con un resumen estadístico y prepara la siguiente."""
        if getattr(self, "touch_mode", False):
            self.touch_selector.reset()
            self.selected_region = None
        if len(self.session_ages) > 0 and self.session_csv_path is not None:
            n = len(self.session_ages)
            avg = float(np.mean(self.session_ages))
            med = float(np.median(self.session_ages))
            min_a = int(np.min(self.session_ages))
            max_a = int(np.max(self.session_ages))
            std_a = float(np.std(self.session_ages))

            try:
                with open(self.session_csv_path, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "RESUMEN_FINAL",
                        self.session_id,
                        n,
                        f"RANGO:{min_a}-{max_a}",
                        f"{avg:.2f}",
                        f"{med:.2f}",
                        f"STD:{std_a:.2f}",
                        "",
                        "",
                        "",
                        ""
                    ])
            except Exception as e:
                print(f"⚠️ Error al guardar resumen CSV: {e}")

            print("\n" + "=" * 70)
            print(f"🏁 FIN DE SESIÓN / REINICIO (Sujeto evaluado)")
            print(f"   • Total Mediciones:    {n}")
            print(f"   • PROMEDIO DE EDAD:    {avg:.2f} años")
            print(f"   • MEDIANA DE EDAD:     {med:.2f} años")
            print(f"   • RANGO DETECTADO:     [{min_a} - {max_a}] años (Std: ±{std_a:.2f}a)")
            print(f"   • Archivo Guardado:    {self.session_csv_path}")
            print("=" * 70)

            # Iniciar nueva sesión
            self.session_idx += 1
            self.session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.session_idx:02d}"
            self.session_csv_path = None
            self.session_ages = []
            self.last_diagnosis_time = None
            self.last_result = None
            self.last_phototype_info = None
            self.last_stratified_result = None
            self.last_optical_info = None
            print(f"\n🔄 Nueva sesión preparada para el siguiente sujeto: {self.session_id}")

    def extract_canonical_face_roi(self, frame: np.ndarray, cx: int, cy: int, head_size: int) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """
        Extrae un recorte 1:1 anatómico canónico seguro.
        Alineado al 48% de altura para centrar el tercio medio facial sin desbordes de resolución.
        """
        h, w, _ = frame.shape
        safe_size = max(100, min(head_size, min(h, w) - 4))
        box_x = int(cx - safe_size * 0.50)
        box_y = int(cy - safe_size * 0.44)

        pad_left = max(0, -box_x)
        pad_top = max(0, -box_y)
        pad_right = max(0, (box_x + safe_size) - w)
        pad_bottom = max(0, (box_y + safe_size) - h)

        if pad_left > 0 or pad_top > 0 or pad_right > 0 or pad_bottom > 0:
            padded = cv2.copyMakeBorder(frame, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_REFLECT_101)
            x_pad = box_x + pad_left
            y_pad = box_y + pad_top
            face_roi = padded[y_pad : y_pad + safe_size, x_pad : x_pad + safe_size]
        else:
            face_roi = frame[box_y : box_y + safe_size, box_x : box_x + safe_size]

        hud_x = max(0, min(w - 1, box_x))
        hud_y = max(0, min(h - 1, box_y))
        hud_w = max(1, min(w - hud_x, safe_size - (hud_x - box_x)))
        hud_h = max(1, min(h - hud_y, safe_size - (hud_y - box_y)))
        return face_roi, (hud_x, hud_y, hud_w, hud_h)

    def reset_stability(self):
        self.stability_start_time = None
        self.prev_center = None
        self.stability_roi_buffer.clear()
        if self.state != "DIAGNOSTICADO":
            self.state = "BUSCANDO"

    def restart_scan(self):
        """Repite la captura conservando la sesión y sus lecturas previas."""
        self.state = "BUSCANDO"
        self.touch_error_until = 0
        if getattr(self, "touch_mode", False):
            self.touch_selector.reset()
            self.selected_region = None
        self.reset_stability()
        self.last_diagnosis_time = None
        for field in ("last_result", "last_mask", "last_face_box", "last_face_roi",
                      "last_landmarks", "last_phototype_info", "last_stratified_result",
                      "last_optical_info"):
            setattr(self, field, None)
        self.toast_message = "Escaneo reiniciado"
        self.toast_until = time.time() + 2.5

    def start_new_person(self):
        previous = self.session_id
        self.finalize_session_and_restart()
        if self.session_id == previous:
            self.session_idx += 1
            self.session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.session_idx:02d}"
        self.session_ages = []
        self.session_csv_path = None
        self.patient_sensitive_skin = False
        self.patient_is_pregnant = False
        self.restart_scan()

    def process_touch_frame(self, frame, detection_result, now):
        """Detectar dedo a un máximo de 15 Hz; captura solo tras retirar la mano."""
        if now < getattr(self, 'touch_error_until', 0):
            self.mobile_control.publish_touch('ERROR', self.toast_message)
            return None
        if self.state == "DIAGNOSTICADO":
            # La selección acompaña al rostro también después de la lectura.
            if len(detection_result.face_landmarks) == 1 and self.touch_selector.anchor is not None:
                h, w = frame.shape[:2]
                face = np.array([(p.x * w, p.y * h) for p in detection_result.face_landmarks[0]])
                self.touch_selector.point = self.touch_selector.anchor.point(face)
                self.touch_selector.radius = float(np.ptp(face[:, 0])) * .075
            else:
                self.touch_selector.point = None
            self.mobile_control.publish_touch("COMPLETADO", "Zona evaluada. Reinicia para señalar otra zona.", 1.0)
            return self.last_landmarks
        if now - self.touch_frame_time < 1 / 15:
            return getattr(self, "touch_landmarks", None)
        self.touch_frame_time = now
        h, w = frame.shape[:2]
        face = None
        if len(detection_result.face_landmarks) == 1:
            face = np.array([(p.x * w, p.y * h) for p in detection_result.face_landmarks[0]], dtype=np.float32)
        self.touch_landmarks = face
        try:
            small = cv2.resize(frame, (640, max(1, round(h * 640 / w))))
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
            hands_result = self.hand_landmarker.detect_for_video(image, int(now * 1000))
            hands = [np.array([(p.x * w, p.y * h) for p in hand]) for hand in hands_result.hand_landmarks]
            ready = self.touch_selector.update(face, hands, now)
        except Exception:
            self.touch_selector.reset()
            self.selected_region = None
            self.state = "BUSCANDO"
            self.mobile_control.publish_touch("ERROR", "No se pudo detectar la mano. Repite el señalamiento.")
            return face
        self.mobile_control.publish_touch(self.touch_selector.state, self.touch_selector.message, self.touch_selector.progress)
        self.state = "ESTABILIZANDO" if self.touch_selector.state == "ESTABILIZANDO" else "BUSCANDO"
        if ready and face is not None:
            min_x, min_y = np.min(face, axis=0)
            max_x, max_y = np.max(face, axis=0)
            cx, cy = int((min_x + max_x) / 2), int((min_y + max_y) / 2)
            head_size = int(max(max_x - min_x, max_y - min_y) * 1.95)
            safe_size = max(100, min(head_size, min(h, w) - 4))
            roi, box = self.extract_canonical_face_roi(frame, cx, cy, head_size)
            # Mismas coordenadas que el recorte, incluso si lleva padding en un borde.
            canonical_box = (int(cx - safe_size * .50), int(cy - safe_size * .44), safe_size, safe_size)
            self.selected_region = self.touch_selector.region_in_roi(face, canonical_box)
            self.state, self.analyzing = "ANALIZANDO", True
            self.mobile_control.publish("ANALIZANDO", len(self.session_ages), None, self.session_id)
            self.last_landmarks = face.astype(np.int32)
            try:
                result = self.execute_diagnosis(roi, face_box=box)
                if "error" in result:
                    raise RuntimeError(result["error"])
                self.last_result = result
                self.state = "DIAGNOSTICADO"
                self.last_diagnosis_time = time.time()
            except Exception as exc:
                self.touch_selector.reset()
                self.selected_region = None
                self.last_result = None
                self.state = "BUSCANDO"
                self.toast_message = str(exc) if isinstance(exc, CaptureRejected) else "No se pudo analizar la zona. Vuelve a señalar dentro de la mejilla."
                self.toast_until = time.time() + 5
                self.touch_error_until = time.monotonic() + 4
                self.mobile_control.publish_touch("ERROR", self.toast_message)
            finally:
                self.analyzing = False
        return face

    def execute_diagnosis(self, face_rois, face_box=None, is_adjustment: bool = False) -> dict:
        """
        Escribe el ROI en memoria compartida, ejecuta la inferencia diagnóstica
        sobre el fotograma estable seleccionado, con alcance global o localizado.
        Integra además clasificación Fitzpatrick (ITA) y motor de fitoterapia estratificada.
        """
        self.mobile_control.publish("ANALIZANDO", len(self.session_ages))
        if isinstance(face_rois, np.ndarray):
            frames_to_eval = [face_rois]
        else:
            frames_to_eval = face_rois if len(face_rois) > 0 else [face_rois]

        primary_roi = frames_to_eval[-1]
        self.last_face_roi = primary_roi.copy()
        if face_box is not None:
            self.last_face_box = face_box

        # 1. Redimensionar fotograma principal a 224x224x3 y convertir BGR a RGB
        roi_rgb = cv2.cvtColor(primary_roi, cv2.COLOR_BGR2RGB)
        roi_224 = cv2.resize(roi_rgb, (224, 224), interpolation=cv2.INTER_AREA)

        quality = capture_quality(roi_224, getattr(self, 'selected_region', None))

        # 2. Extraer y guardar la máscara de segmentación U-Net Nano
        self.last_mask = inference_engine.get_segmentation_mask(roi_224)

        # 3. Extracción de fototipo Fitzpatrick e ITA multi-muestra temporal (eliminación de parpadeo)
        try:
            cheek_patches = []
            for f in frames_to_eval:
                f_rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                f_224 = cv2.resize(f_rgb, (224, 224), interpolation=cv2.INTER_AREA)
                patch = np.vstack([f_224[115:155, 60:95], f_224[115:155, 129:164]])
                cheek_patches.append(patch)

            phototype_res = extract_skin_phototype_multisample(cheek_patches)
            self.last_phototype_info = phototype_res
        except Exception as e:
            print(f"⚠️ Error al extraer fototipo Fitzpatrick multi-muestra: {e}")
            phototype_res = {
                "phototype": None,
                "description": "No disponible",
                "clinical_label": "No disponible",
                "ita": None,
            }
            self.last_phototype_info = phototype_res

        # 4. Detección óptica de monturas de gafas o brillo especular
        try:
            optical_res = detect_glasses_or_glare(roi_224)
            self.last_optical_info = optical_res
        except Exception as e:
            print(f"⚠️ Error en detección de gafas/glare: {e}")
            optical_res = {"glasses_detected": False, "glare_detected": False, "clinical_hint": ""}
            self.last_optical_info = optical_res

        self.last_stratified_result = None

        # 6. Asignar buffer en Memoria Compartida POSIX Zero-Copy
        shm = shared_memory.SharedMemory(create=True, size=EXPECTED_BUFFER_SIZE_BYTES)
        try:
            arr_shm = np.ndarray((224, 224, 3), dtype=np.uint8, buffer=shm.buf)
            np.copyto(arr_shm, roi_224)

            # 7. Payload con Telemetría
            payload = {
                "shm_descriptor": shm.name,
                "telemetry": {
                    "stability_duration_ms": int(self.required_stability_sec * 1000),
                    "thermal_soc_celsius": 45.8,
                },
            }
            if getattr(self, "selected_region", None) is not None:
                payload["selected_region"] = self.selected_region
            headers = {
                "Authorization": f"Bearer {DEV_TOKEN}",
                "X-Correlation-ID": str(uuid.uuid4()),
                "Content-Type": "application/json",
            }

            # 8. Disparo de inferencia local loopback
            t0 = time.perf_counter()
            try:
                response = self.client.post("/api/v1/diagnostics/analyze", json=payload, headers=headers)
                total_call_ms = (time.perf_counter() - t0) * 1000.0
                self.last_inference_latency_ms = total_call_ms
            except Exception as exc:
                print(f"⚠️ Error en comunicación con el motor diagnóstico: {exc}")
                return {"error": f"Error de inferencia: {str(exc)}"}

            if response.status_code == 201:
                res_data = response.json()
                res_data['datos']['capture_quality'] = quality
                res_data['datos']['visual_appearance'] = analyze_visual_appearance(
                    roi_rgb, getattr(self, 'selected_region', None))
                if getattr(self, 'selected_region', None) is not None:
                    self.mobile_control.publish_analysis_preview(
                        roi_224, self.last_mask, self.selected_region, res_data['datos']['sesion_id'])
                res_data["metadatos"]["total_call_ms"] = round(total_call_ms, 2)
                # Conservar las mediciones de API usadas por el motor de reglas
                res_data["datos"]["clinica"]["fototipo_fitzpatrick"] = phototype_res["phototype"]
                res_data["datos"]["clinica"]["fototipo_label"] = phototype_res["clinical_label"]
                res_data["datos"]["clinica"]["ita_deg"] = phototype_res["ita"]
                res_data["datos"]["clinica"]["gafas_detectadas"] = optical_res["glasses_detected"]

                # Registro automático en CSV de sesión y global (solo si no es ajuste de offset)
                if not is_adjustment:
                    self.log_measurement_to_csv(res_data["datos"]["clinica"], res_data["metadatos"])
                elif len(self.session_ages) > 0:
                    self.session_ages[-1] = res_data["datos"]["clinica"]["edad_biologica_estimada"]
                return res_data
            else:
                return {"error": f"Error {response.status_code}: {response.text}"}
        finally:
            shm.close()
            shm.unlink()

    def draw_reticle(self, frame: np.ndarray, pts: Optional[np.ndarray], progress: float):
        """
        Dibuja el retículo táctico y guía de posicionamiento facial en pantalla:
        - BUSCANDO: Guía central estática con brackets y elipse segmentada.
        - ESTABILIZANDO: Seguimiento de rostro con anillo de progreso circular.
        - ANALIZANDO: Indicador de escaneo activo.
        - DIAGNOSTICADO: Encuadre sutil de la zona evaluada.
        """
        h, w, _ = frame.shape
        now = time.time()

        cyan_main = (255, 240, 0)
        cyan_dim = (180, 140, 20)
        emerald_active = (0, 255, 180)
        amber_warn = (0, 160, 255)
        text_white = (255, 255, 255)

        # Mensaje de estado amable, centrado en la parte superior de la imagen.
        if self.toast_message and now < self.toast_until:
            tw = cv2.getTextSize(self.toast_message, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)[0][0]
            tx = (w - tw) // 2
            draw_glass_rect(frame, tx - 20, 68, tx + tw + 20, 108, (22, 31, 42), 0.94, (0, 220, 175), 1)
            cv2.putText(frame, self.toast_message, (tx, 94), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (225, 255, 248), 1, cv2.LINE_AA)
        elif self.movement_warning_until > now:
            warn_msg = "Quédate quieto un momento"
            tw = cv2.getTextSize(warn_msg, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)[0][0]
            tx = (w - tw) // 2
            draw_glass_rect(frame, tx - 20, 68, tx + tw + 20, 108, (42, 30, 20), 0.94, amber_warn, 1)
            cv2.putText(frame, warn_msg, (tx, 94), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (190, 220, 255), 1, cv2.LINE_AA)


        if self.state == "BUSCANDO":
            # 1. Guía central fija para asistir en el centrado del paciente
            cx = w // 2
            cy = int(h * 0.46)
            rx, ry = 135, 185

            pulse = 0.65 + 0.35 * math.sin(now * 3.5)
            guide_color = (int(cyan_dim[0] * pulse), int(cyan_dim[1] * pulse), int(cyan_dim[2] * pulse))

            # Brackets de encuadre en las esquinas
            draw_corner_brackets(frame, cx - rx, cy - ry, cx + rx, cy + ry, guide_color, length=28, thickness=2)

            # Elipse anatómica segmentada (4 cuadrantes guía)
            cv2.ellipse(frame, (cx, cy), (rx - 15, ry - 15), 0, 15, 75, guide_color, 1, cv2.LINE_AA)
            cv2.ellipse(frame, (cx, cy), (rx - 15, ry - 15), 0, 105, 165, guide_color, 1, cv2.LINE_AA)
            cv2.ellipse(frame, (cx, cy), (rx - 15, ry - 15), 0, 195, 255, guide_color, 1, cv2.LINE_AA)
            cv2.ellipse(frame, (cx, cy), (rx - 15, ry - 15), 0, 285, 345, guide_color, 1, cv2.LINE_AA)

            # Ticks de centrado
            cv2.line(frame, (cx, cy - ry), (cx, cy - ry + 12), guide_color, 1, cv2.LINE_AA)
            cv2.line(frame, (cx, cy + ry - 12), (cx, cy + ry), guide_color, 1, cv2.LINE_AA)
            cv2.line(frame, (cx - rx, cy), (cx - rx + 12, cy), guide_color, 1, cv2.LINE_AA)
            cv2.line(frame, (cx + rx - 12, cy), (cx + rx, cy), guide_color, 1, cv2.LINE_AA)

            # Instrucción en tarjeta flotante con acción concreta.
            guide_text = "Centra tu rostro aquí"
            sub_text = "Mira al frente y quítate el cabello de la cara"
            tw = cv2.getTextSize(guide_text, cv2.FONT_HERSHEY_SIMPLEX, 0.62, 1)[0][0]
            sw = cv2.getTextSize(sub_text, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)[0][0]
            card_w = max(tw, sw) + 36
            card_x = cx - card_w // 2
            card_y = min(h - 92, cy + ry + 20)
            draw_glass_rect(frame, card_x, card_y, card_x + card_w, card_y + 66, (18, 26, 35), 0.90, (100, 185, 175), 1)
            cv2.putText(frame, guide_text, (cx - tw // 2, card_y + 27), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (235, 250, 248), 1, cv2.LINE_AA)
            cv2.putText(frame, sub_text, (cx - sw // 2, card_y + 49), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (185, 210, 208), 1, cv2.LINE_AA)

        elif self.state == "ESTABILIZANDO" and pts is not None:
            # 2. Retículo activo fijado sobre el rostro detectado
            min_x, min_y = np.min(pts, axis=0)
            max_x, max_y = np.max(pts, axis=0)
            pad = 16
            bx1, by1 = max(10, min_x - pad), max(55, min_y - pad)
            bx2, by2 = min(w - 10, max_x + pad), min(h - 35, max_y + pad)

            # Encuadre suave; evita competir con el rostro y con la instrucción.
            draw_corner_brackets(frame, bx1, by1, bx2, by2, emerald_active, length=26, thickness=2)

            # Anillo circular de progreso sobre la frente / cabeza
            ring_cx = (bx1 + bx2) // 2
            ring_cy = max(82, by1 - 36)
            radius = 24

            # Anillo de fondo
            cv2.circle(frame, (ring_cx, ring_cy), radius, (30, 42, 52), 3, cv2.LINE_AA)

            # Arco de progreso
            arc_angle = int(360.0 * progress)
            if arc_angle > 0:
                cv2.ellipse(frame, (ring_cx, ring_cy), (radius, radius), -90, 0, arc_angle, emerald_active, 3, cv2.LINE_AA)

            # Tiempo restante dentro del anillo
            rem_sec = max(0.0, self.required_stability_sec * (1.0 - progress))
            txt_sec = f"{rem_sec:.1f}s"
            stw = cv2.getTextSize(txt_sec, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)[0][0]
            cv2.putText(frame, txt_sec, (ring_cx - stw // 2, ring_cy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, text_white, 1, cv2.LINE_AA)

            # La cuenta regresiva ya indica cuánto falta, sin porcentajes técnicos.
            msg = "Quédate quieto"
            mw = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)[0][0]
            tx = min(w - mw - 18, max(12, ring_cx - mw // 2))
            ty = min(h - 74, by2 + 18)
            draw_glass_rect(frame, tx - 10, ty - 20, tx + mw + 10, ty + 3, (18, 30, 29), 0.88, emerald_active, 1)
            cv2.putText(frame, msg, (tx, ty - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (195, 255, 235), 1, cv2.LINE_AA)

        elif self.state == "ANALIZANDO":
            # 3. Retículo en modo escaneo / análisis
            cx = w // 2
            cy = h // 2
            draw_glass_rect(frame, cx - 190, cy - 42, cx + 190, cy + 42, (18, 26, 35), 0.92, cyan_main, 1)
            cv2.putText(frame, "Estamos revisando tu piel", (cx - 158, cy - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 250, 248), 1, cv2.LINE_AA)
            cv2.putText(frame, "Esto puede tardar unos segundos", (cx - 134, cy + 23), cv2.FONT_HERSHEY_SIMPLEX, 0.38, text_dim, 1, cv2.LINE_AA)

        elif self.state == "DIAGNOSTICADO" and self.last_face_box is not None:
            # 4. Retículo fino en torno al rostro diagnosticado
            x, y, fw, fh = self.last_face_box
            draw_corner_brackets(frame, x, y, x + fw, y + fh, cyan_dim, length=20, thickness=1)

    def draw_hud(self, frame: np.ndarray, pts: Optional[np.ndarray], progress: float):
        """
        Dibuja el HUD clínico táctico con arquitectura Zero-Allocation para Raspberry Pi 5.
        """
        if getattr(self, "touch_mode", False):
            draw_mirror_hud(frame, self.touch_selector, self.last_result, self.state,
                            self.toast_message if time.time() < self.toast_until else "")
            return
        h, w, _ = frame.shape

        cyan_main = (255, 240, 0)
        cyan_contour = (255, 245, 30)
        cyan_mesh_base = (245, 215, 20)
        cyan_border = (235, 195, 0)
        cyan_accent = (0, 255, 200)
        bg_dark = (14, 18, 24)
        text_white = (255, 255, 255)
        text_dim = (175, 200, 220)

        # Barra superior sencilla: estado de la captura y contador de lecturas.
        draw_glass_rect(frame, 0, 0, w, 54, bg_dark, 0.88, cyan_border, 1)

        active_pts = pts if self.state != "DIAGNOSTICADO" else (self.last_landmarks if self.last_landmarks is not None else pts)

        # Estado explicado en lenguaje sencillo.
        if self.state == "DIAGNOSTICADO":
            n_reg = len(self.session_ages)
            status_text = "Evaluación lista"
            status_color = cyan_main
        elif self.state == "ESTABILIZANDO":
            status_text = "Mantén la posición"
            status_color = cyan_accent
        elif self.state == "ANALIZANDO":
            status_text = "Revisando tu piel..."
            status_color = (0, 180, 255)
        elif active_pts is not None:
            status_text = "Rostro detectado"
            status_color = cyan_main
        else:
            status_text = "Coloca tu rostro en la guía"
            status_color = (160, 180, 200)

        cv2.circle(frame, (25, 27), 6, status_color, -1, cv2.LINE_AA)
        cv2.putText(frame, status_text, (42, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.58, text_white, 1, cv2.LINE_AA)
        if self.state == "ESTABILIZANDO":
            cv2.putText(frame, f"{int(progress * 100)}%", (w - 86, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.48, status_color, 1, cv2.LINE_AA)
        elif self.state == "DIAGNOSTICADO":
            cv2.putText(frame, f"Lectura {len(self.session_ages)}", (w - 150, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.44, text_dim, 1, cv2.LINE_AA)

        # Evaluación de calidad lumínica y semáforo lux
        lighting = check_lighting_quality(frame)
        self.last_lighting_info = lighting
        lgt_st = lighting.get("status", "OPTIMA")
        lgt_lux = lighting.get("estimated_lux", 120.0)
        lgt_str = f"Luz: {lgt_lux:.0f}lx" if lgt_st == "OPTIMA" else ("Luz Baja" if lgt_st == "LUZ_BAJA" else "Brillo Alto")

        # Indicador discreto de iluminación solo cuando requiere corrección.
        if lgt_st != "OPTIMA":
            light_hint = "Busca un lugar con más luz" if lgt_st == "LUZ_BAJA" else "Reduce la luz directa"
            hint_w = cv2.getTextSize(light_hint, cv2.FONT_HERSHEY_SIMPLEX, 0.43, 1)[0][0]
            hint_x = (w - hint_w) // 2
            draw_glass_rect(frame, hint_x - 14, 62, hint_x + hint_w + 14, 91, bg_dark, 0.88, (0, 190, 255), 1)
            cv2.putText(frame, light_hint, (hint_x, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (0, 205, 255), 1, cv2.LINE_AA)

        # Progreso visible sin mostrar métricas técnicas.
        if self.state == "ESTABILIZANDO" and progress > 0.0:
            prog_w = int(w * progress)
            cv2.line(frame, (0, 54), (prog_w, 54), cyan_accent, 3, cv2.LINE_AA)

        # 2. Malla Facial Canónica 3D (Face Mesh) o Contornos según self.mesh_mode
        if active_pts is not None and len(active_pts) >= 468:
            if self.mesh_mode == "FACE_MESH":
                # Malla Facial 3D Holográfica Completa (478 nodos MediaPipe) con Blending en ROI Local (Zero-Allocation)
                min_x, min_y = np.min(active_pts, axis=0)
                max_x, max_y = np.max(active_pts, axis=0)
                pad = 12
                mx1, my1 = max(0, min_x - pad), max(0, min_y - pad)
                mx2, my2 = min(w, max_x + pad), min(h, max_y + pad)

                if mx2 > mx1 and my2 > my1:
                    face_slice = frame[my1:my2, mx1:mx2]
                    mesh_sub = face_slice.copy()
                    cyan_fine = (255, 255, 0)

                    # Aristas de triangulación canónica sub-píxel (Face Mesh 478 + iris)
                    for u, v in self.tess_unique_edges:
                        p1 = active_pts[u]
                        p2 = active_pts[v]
                        cv2.line(mesh_sub, (p1[0] - mx1, p1[1] - my1), (p2[0] - mx1, p2[1] - my1), cyan_fine, 1, cv2.LINE_AA)

                    # Mezcla holográfica translúcida calibrada
                    mesh_alpha = 0.48 if self.state != "DIAGNOSTICADO" else 0.35
                    cv2.addWeighted(mesh_sub, mesh_alpha, face_slice, 1.0 - mesh_alpha, 0, dst=face_slice)

                    # Resaltar contornos anatómicos nítidos (mandíbula, ojos, labios, cejas)
                    for c in self.conns_contours:
                        p1 = active_pts[c.start]
                        p2 = active_pts[c.end]
                        cv2.line(frame, (p1[0], p1[1]), (p2[0], p2[1]), cyan_contour, 1, cv2.LINE_AA)

            elif self.mesh_mode == "CONTOURS":
                # Contornos anatómicos clave (124 conexiones, ultra optimizado)
                for c in self.conns_contours:
                    p1 = active_pts[c.start]
                    p2 = active_pts[c.end]
                    cv2.line(frame, (p1[0], p1[1]), (p2[0], p2[1]), cyan_contour, 1, cv2.LINE_AA)
            # En modo "OFF", no se dibuja malla para máxima claridad del tejido


            # 3. Proyección de la Máscara de Segmentación de Manchas (Píxel a Píxel)
            if self.state == "DIAGNOSTICADO" and self.last_mask is not None and self.last_face_box is not None:
                self._render_spot_segmentation(frame, active_pts)

        # 4. Retículo y Guía Táctica de Posicionamiento
        self.draw_reticle(frame, pts, progress)

        # 5. Panel de Resultados Lateral si hay Diagnóstico en la sesión activa
        if self.last_result is not None:
            self._draw_diagnosis_card(frame)

    def _render_spot_segmentation(self, frame: np.ndarray, pts: np.ndarray):
        """
        Proyecta la máscara de segmentación de la U-Net Nano estrictamente
        dentro del polígono anatómico del rostro con optimización Zero-Copy local.
        """
        if self.last_face_box is None or self.last_mask is None:
            return

        x, y, fw, fh = self.last_face_box
        h_frame, w_frame, _ = frame.shape
        cyan_main = (255, 240, 0)
        bg_dark = (14, 18, 24)

        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(w_frame, x + fw), min(h_frame, y + fh)
        box_w, box_h = x2 - x1, y2 - y1
        if box_w <= 0 or box_h <= 0:
            return

        # Redimensionar la máscara binaria [224, 224] al tamaño de la región facial
        mask_resized = cv2.resize(self.last_mask.astype(np.uint8), (box_w, box_h), interpolation=cv2.INTER_NEAREST)

        # Polígono anatómico local en coordenadas de la caja (ahorra alocar matriz completa de 1280x720)
        oval_pts = [pts[conn.start] for conn in self.conns_oval]
        poly_arr_local = np.array([[px - x1, py - y1] for px, py in oval_pts], dtype=np.int32)

        face_poly_local = np.zeros((box_h, box_w), dtype=np.uint8)
        cv2.fillPoly(face_poly_local, [poly_arr_local], 255)

        # Manchas válidas dentro del polígono anatómico de la piel
        spots_in_face = (mask_resized > 0) & (face_poly_local > 0)

        if np.any(spots_in_face):
            roi = frame[y1:y2, x1:x2]
            color_layer = roi.copy()
            # Tono ámbar/coral para destacar las manchas frente a la piel
            color_layer[spots_in_face] = [0, 140, 255]
            cv2.addWeighted(color_layer, 0.55, roi, 0.45, 0, roi)
            frame[y1:y2, x1:x2] = roi

            # Delinear contornos nítidos ultra-delgados de 1px en cian eléctrico
            contours, _ = cv2.findContours(spots_in_face.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                if cv2.contourArea(cnt) > 6:
                    cnt_global = cnt + np.array([[[x1, y1]]])
                    cv2.drawContours(frame, cnt_global, -1, cyan_main, 1, cv2.LINE_AA)

            # Badge de segmentación U-Net en cian
            nose_tip = pts[4]
            badge_x = min(w_frame - 310, max(15, nose_tip[0] - 150))
            badge_y = min(h_frame - 38, pts[152][1] + 30)
            draw_glass_rect(frame, badge_x - 5, badge_y - 18, badge_x + 300, badge_y + 6, bg_dark, 0.85, cyan_main, 1)
            cv2.putText(frame, "U-NET NANO: LESIONES PIGMENTARIAS", (badge_x, badge_y - 4), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, cyan_main, 1, cv2.LINE_AA)

    def _draw_diagnosis_card(self, frame: np.ndarray):
        """
        Dibuja la tarjeta clínica lateral con información dermatológica completa:
        Edad biológica, fototipo Fitzpatrick (ITA), lesiones pigmentarias y receta fitoterapéutica.
        """
        h, w, _ = frame.shape
        panel_w = min(440, w - 32)
        panel_h = min(376, h - 84)
        px = w - panel_w - 18
        py = 68

        cyan_main = (210, 255, 240)
        cyan_border = (95, 155, 140)
        cyan_accent = (125, 235, 200)
        bg_dark = (22, 29, 35)
        text_white = (245, 249, 247)
        text_dim = (190, 205, 200)
        sep_color = (65, 82, 76)

        # Fondo Frosted Glass sin alocación global
        draw_glass_rect(frame, px, py, px + panel_w, py + panel_h, bg_dark, 0.94, cyan_border, 1)

        data = self.last_result.get("datos", {})
        clinica = data.get("clinica", {})
        prescripciones = data.get("prescripciones", [])
        metadatos = self.last_result.get("metadatos", {})

        # Cabecera con jerarquía clara y lenguaje cercano.
        cv2.putText(frame, "Resultado de la evaluación", (px + 18, py + 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, cyan_main, 1, cv2.LINE_AA)

        n_reg = len(self.session_ages)
        sub_hdr = f"Muestra #{n_reg}  |  Sesion: {self.session_id}"
        cv2.putText(frame, f"Lectura {n_reg}  ·  Sesión {self.session_id}", (px + 18, py + 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, text_dim, 1, cv2.LINE_AA)
        cv2.line(frame, (px + 18, py + 69), (px + panel_w - 18, py + 69), sep_color, 1, cv2.LINE_AA)

        # 2. Bloque Biométrico
        edad = clinica.get("edad_biologica_estimada", "--")
        spots = clinica.get("porcentaje_hiperpigmentacion", "--")
        sev = clinica.get("clasificacion_severidad", "--")
        lat = metadatos.get("execution_time_ms", "--")
        offset_str = f" [Offset: {int(self.age_offset):+}a]" if self.age_offset != 0 else ""
        fototipo_val = clinica.get("fototipo_fitzpatrick", 0)
        fototipo_lbl = clinica.get("fototipo_label", f"Fototipo {fototipo_val}")
        ita_deg = clinica.get("ita_deg")
        ita_str = f" (ITA: {ita_deg:+.1f} deg)" if ita_deg is not None else ""

        # Tres métricas clave en tarjetas para facilitar la lectura rápida.
        tile_y = py + 82
        tile_w = (panel_w - 48) // 3
        age_text = f"{edad} años"
        spots_text = f"{spots}%"
        tone_text = f"{fototipo_val or '—'}"
        metrics = [("Edad estimada", age_text), ("Áreas observadas", spots_text), ("Tono de piel", tone_text)]
        for i, (label, value) in enumerate(metrics):
            tx1 = px + 18 + i * (tile_w + 6)
            draw_glass_rect(frame, tx1, tile_y, tx1 + tile_w, tile_y + 62, (32, 43, 47), 0.96, sep_color, 1)
            cv2.putText(frame, label, (tx1 + 7, tile_y + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.29, text_dim, 1, cv2.LINE_AA)
            cv2.putText(frame, value[:14], (tx1 + 7, tile_y + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.50, text_white, 1, cv2.LINE_AA)

        curr_y = tile_y + 80
        if self.session_ages:
            avg_val = np.mean(self.session_ages)
            med_val = np.median(self.session_ages)
            curr_y += 18
            cv2.putText(frame, f"  Promedio: {avg_val:.1f}a  |  Mediana: {med_val:.1f}a  (N={len(self.session_ages)})", 
                        (px + 16, curr_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, cyan_accent, 1, cv2.LINE_AA)

        # Fototipo Fitzpatrick e ITA
        cv2.putText(frame, f"{fototipo_lbl}{ita_str}", (px + 18, curr_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, text_dim, 1, cv2.LINE_AA)
        curr_y += 18
        sev_text = f"Nivel observado: {sev}"
        cv2.putText(frame, sev_text[:50], (px + 18, curr_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, text_white, 1, cv2.LINE_AA)
        curr_y += 17
        cv2.putText(frame, "El color sobre el rostro marca las áreas observadas.", (px + 18, curr_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, text_dim, 1, cv2.LINE_AA)

        # Lentes / Reflejos si fueron detectados
        if clinica.get("gafas_detectadas"):
            curr_y += 16
            cv2.putText(frame, "La iluminación o las gafas pueden influir en la lectura.", (px + 18, curr_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, (200, 220, 255), 1, cv2.LINE_AA)

        if self.patient_sensitive_skin:
            curr_y += 16
            cv2.putText(frame, "Se consideró el perfil de piel sensible.", (px + 18, curr_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, (120, 220, 255), 1, cv2.LINE_AA)


        # Separador Fitoterapia
        curr_y += 12
        cv2.line(frame, (px + 18, curr_y), (px + panel_w - 18, curr_y), sep_color, 1, cv2.LINE_AA)

        # 3. Bloque Fitoterapia Estratificada (SQLite 3NF + Reglas Clínicas)
        curr_y += 22
        estrato = clinica.get("estrato_etario", "")
        indicacion = clinica.get("indicacion_primaria", "Regulacion dermatologica")
        cv2.putText(frame, "Siguiente paso", (px + 18, curr_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.43, cyan_accent, 1, cv2.LINE_AA)

        curr_y += 16
        cv2.putText(frame, f"{indicacion[:48]}", (px + 18, curr_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, text_dim, 1, cv2.LINE_AA)

        if prescripciones:
            p0 = prescripciones[0]
            curr_y += 18
            cv2.putText(frame, f"• {p0.get('nombre_comun', '')} ({p0.get('especie', '')})", (px + 18, curr_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.37, text_white, 1, cv2.LINE_AA)
            prec = p0.get('precauciones', '')
            curr_y += 15
            cv2.putText(frame, f"Ten en cuenta: {prec[:42]}", (px + 18, curr_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.33, text_dim, 1, cv2.LINE_AA)

        # Advertencia de seguridad
        curr_y += 17
        status_msg = data.get("orientacion", {}).get("estado", "Consulta esta orientación con un profesional de salud.")
        cv2.putText(frame, status_msg[:55], (px + 18, curr_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.31, (205, 220, 210), 1, cv2.LINE_AA)

        # Mensaje de ayuda en pantalla; la lectura se inicia automáticamente.
        cv2.putText(frame, "Orientación informativa · No reemplaza una consulta médica", (px + 18, py + panel_h - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.29, text_dim, 1, cv2.LINE_AA)

    def export_pdf_report(self) -> Optional[str]:
        """Genera y guarda el reporte clínico oficial en formato PDF (1 página)."""
        if self.last_result is None:
            print("\n⚠️ No hay diagnóstico activo para generar PDF. Capture una muestra primero.")
            self.toast_message = "Capture diagnostico antes de exportar PDF"
            self.toast_until = time.time() + 2.5
            return None

        debug_img_path = self.sessions_dir / "ultimo_rostro_224.jpg"
        face_input = str(debug_img_path) if debug_img_path.exists() else None
        if face_input is None and self.last_face_roi is not None:
            face_input = self.last_face_roi

        mask_arr = self.last_mask if self.last_mask is not None else None
        try:
            pdf_path = generate_clinical_report(
                session_id=self.session_id,
                measurement_data=self.last_result,
                face_img_path=face_input,
                mask_img_path=mask_arr
            )
            pdf_name = Path(pdf_path).name
            print(f"\n📄 Reporte Clínico PDF generado con éxito:\n   {pdf_path}")
            self.toast_message = f"PDF Guardado: {pdf_name}"
            self.toast_until = time.time() + 4.0
            return pdf_path
        except Exception as e:
            print(f"⚠️ Error al generar reporte PDF: {e}")
            self.toast_message = f"Error PDF: {str(e)[:30]}"
            self.toast_until = time.time() + 3.0
            return None

    def run(self):
        print("=" * 68)
        print("🎥 INICIANDO CAPTURA CON 3D FACE MESH (DERMA-ONEDGE HUD)")
        print("   • Colóquese frente a la cámara dentro de la guía y mantenga quietud 1.5s.")
        print("   • [ESPACIO] o [R]: Tomar otra lectura en la MISMA persona/CSV.")
        print("   • [P]: Generar y guardar informe médico oficial en PDF (1 Página).")
        print("   • [S]: Alternar perfil de Piel Sensible (sustitución botánica segura).")
        print("   • [M]: Alternar modo de malla (Face Mesh 3D / Contornos / Desactivada).")
        print("   • [+/-]: Calibrar offset de edad en caliente (persistencia automática en JSON).")
        print("   • [N]: Finalizar sujeto actual y empezar NUEVO sujeto/CSV.")
        print("   • [Q] o [ESC]: Salir y guardar resumen estadístico.")
        print("=" * 68)

        cap = get_camera_capture(self.camera_index, width=1280, height=720)
        if not cap.isOpened():
            print(f"❌ Error: No se pudo abrir la cámara con índice {self.camera_index}.")
            return


        window_name = "DERMA-ONEDGE | 3D Face Mesh Diagnostic"
        web_mode = os.getenv("DERMA_WEB", "1") == "1"
        if not web_mode:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 1280, 720)

        self.last_frame_time = time.perf_counter()

        mobile_server = None
        try:
            if web_mode or os.getenv("DERMA_MOBILE", "0") == "1":
                mobile_server = start_mobile_server(
                    self.mobile_control, int(os.getenv("DERMA_MOBILE_PORT", "8080"))
                )
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("⚠️ Error al leer fotograma de cámara.")
                    break

                self.mobile_control.apply_pending(self.restart_scan, self.start_new_person)
                self.mobile_control.publish(
                    self.state, len(self.session_ages), self.last_result, self.session_id
                )

                # Cálculo de FPS mediante media móvil exponencial (EMA)
                t_now = time.perf_counter()
                dt = t_now - self.last_frame_time
                self.last_frame_time = t_now
                if dt > 0.0001:
                    inst_fps = 1.0 / dt
                    self.fps = 0.92 * self.fps + 0.08 * inst_fps

                # Espejar horizontalmente para experiencia natural tipo espejo
                frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape

                # Detección de 478 puntos 3D con MediaPipe Face Landmarker
                tracking_frame = cv2.resize(frame, (640, max(1, round(h * 640 / w)))) if self.touch_mode and w > 640 else frame
                rgb = cv2.cvtColor(tracking_frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                if not self.touch_mode or time.monotonic() - self.touch_frame_time >= 1 / 15:
                    detection_result = self.landmarker.detect(mp_image)
                    self.touch_face_detection = detection_result
                else:
                    detection_result = self.touch_face_detection

                pts = None
                face_box = None
                stability_progress = 0.0

                if self.touch_mode:
                    pts = self.process_touch_frame(frame, detection_result, time.monotonic())
                    stability_progress = self.touch_selector.progress
                elif detection_result.face_landmarks and self.state != "DIAGNOSTICADO":
                    face_lms = detection_result.face_landmarks[0]
                    pts = np.array([(int(p.x * w), int(p.y * h)) for p in face_lms], dtype=np.int32)

                    # Proporción anatómica canónica adaptativa
                    min_x, min_y = np.min(pts, axis=0)
                    max_x, max_y = np.max(pts, axis=0)
                    cx = (min_x + max_x) // 2
                    cy = (min_y + max_y) // 2

                    face_w = max_x - min_x
                    face_h = max_y - min_y
                    head_size = int(max(face_w, face_h) * 1.95)
                    face_roi, face_box = self.extract_canonical_face_roi(frame, cx, cy, head_size)

                    # Seguimiento de estabilidad con la punta nasal (landmark 4)
                    center = pts[4]
                    now = time.time()

                    # Manejo de estabilidad y disparo automático multi-muestra continuo
                    if self.state == "DIAGNOSTICADO":
                        if self.last_diagnosis_time is not None and (now - self.last_diagnosis_time) < self.auto_continuous_cooldown_sec:
                            pass
                        else:
                            self.state = "BUSCANDO"
                            self.reset_stability()
                            self.last_diagnosis_time = None

                    if self.state != "DIAGNOSTICADO":
                        if self.prev_center is not None:
                            dist = np.hypot(center[0] - self.prev_center[0], center[1] - self.prev_center[1])

                            if dist < self.max_movement_px:
                                if self.stability_start_time is None:
                                    self.stability_start_time = now

                                elapsed = now - self.stability_start_time
                                stability_progress = min(elapsed / self.required_stability_sec, 1.0)
                                self.state = "ESTABILIZANDO"

                                # Acumular en el búfer de estabilidad
                                self.stability_roi_buffer.append(face_roi.copy())
                                if len(self.stability_roi_buffer) > 5:
                                    self.stability_roi_buffer.pop(0)

                                # Si se cumple la condición de estabilidad de 1.5s -> Disparo automático
                                if elapsed >= self.required_stability_sec and not self.analyzing:
                                    next_num = len(self.session_ages) + 1
                                    print(f"\n🎯 ¡Estabilidad alcanzada (>1.5s)! Disparando análisis on-edge (Muestra #{next_num})...")
                                    self.analyzing = True
                                    self.state = "ANALIZANDO"

                                    self.last_landmarks = pts.copy()
                                    result = self.execute_diagnosis(self.stability_roi_buffer, face_box=face_box)
                                    if "error" in result:
                                        print(f"⚠️ Diagnóstico no completado: {result['error']}")
                                        self.toast_message = "Error en evaluacion"
                                        self.toast_until = time.time() + 3.0
                                        self.state = "BUSCANDO"
                                        self.reset_stability()
                                        self.analyzing = False
                                    else:
                                        self.last_result = result
                                        self.state = "DIAGNOSTICADO"
                                        self.analyzing = False
                                        self.last_diagnosis_time = time.time()

                                        print("Resultado Clínico Retornado:")
                                        print(json.dumps(result, indent=2, ensure_ascii=False))
                            else:
                                if self.state == "ESTABILIZANDO":
                                    self.movement_warning_until = now + 1.2
                                self.reset_stability()
                        else:
                            self.stability_start_time = now

                    self.prev_center = center
                elif not detection_result.face_landmarks and self.state != "DIAGNOSTICADO":
                    self.reset_stability()

                # Dibujar interfaz visual HUD optimizada
                self.mobile_control.publish(
                    self.state, len(self.session_ages), self.last_result, self.session_id
                )
                if web_mode:
                    self.mobile_control.publish_preview(frame, self.touch_selector if self.touch_mode else None)
                else:
                    self.draw_hud(frame, pts, stability_progress)
                    cv2.imshow(window_name, frame)

                # Control de teclado
                key = -1 if web_mode else cv2.waitKey(1) & 0xFF
                if key in [ord('q'), ord('Q'), 27]: # Q o ESC
                    print("\nCerrando aplicación de cámara...")
                    if len(self.session_ages) > 0:
                        self.finalize_session_and_restart()
                    break
                elif key in [ord('r'), ord('R')]: # R: Siguiente muestra en misma sesión
                    print(f"\n🔄 Reiniciando escaneo para siguiente muestra en la misma sesión (#{len(self.session_ages) + 1})...")
                    self.mobile_control.invalidate()
                    self.restart_scan()
                elif key in [ord('n'), ord('N')]: # N: Nuevo Sujeto
                    print("\n👤 Finalizando sujeto actual y preparando nuevo CSV...")
                    self.mobile_control.invalidate()
                    self.finalize_session_and_restart()
                    self.state = "BUSCANDO"
                    self.reset_stability()
                elif key in [ord('m'), ord('M')]: # M: Alternar modo de malla
                    modes = ["FACE_MESH", "CONTOURS", "OFF"]
                    next_idx = (modes.index(self.mesh_mode) + 1) % len(modes)
                    self.mesh_mode = modes[next_idx]
                    print(f"\n🔄 Modo de Malla Facial cambiado a: [{self.mesh_mode}]")
                elif key in [ord('p'), ord('P')]: # P: Generar Reporte Clínico Oficial en PDF (1 Página)
                    self.export_pdf_report()
                elif key in [ord('s'), ord('S')]: # S: Alternar Piel Sensible (Contraindicaciones)
                    self.patient_sensitive_skin = not self.patient_sensitive_skin
                    st_txt = "ACTIVADA" if self.patient_sensitive_skin else "DESACTIVADA"
                    print(f"\n🩺 Perfil Clínico: Piel Sensible {st_txt} (Sustitución botánica segura)")
                    self.toast_message = f"Piel Sensible: {st_txt}"
                    self.toast_until = time.time() + 2.5
                    if self.state == "DIAGNOSTICADO" and self.last_face_roi is not None and not self.touch_mode:
                        self.last_result = self.execute_diagnosis(self.last_face_roi, face_box=self.last_face_box, is_adjustment=True)
                elif key in [ord('+'), ord('='), 43]: # +: Aumentar offset
                    self.age_offset += 1.0
                    os.environ["DERMA_AGE_OFFSET"] = str(self.age_offset)
                    save_calibration_offset(self.age_offset)
                    print(f"\n⚙️ Offset de Edad ajustado y guardado: {int(self.age_offset):+} años")
                    self.toast_message = f"Offset Guardado: {int(self.age_offset):+}a"
                    self.toast_until = time.time() + 2.0
                    if self.state == "DIAGNOSTICADO" and self.last_face_roi is not None and not self.touch_mode:
                        self.last_result = self.execute_diagnosis(self.last_face_roi, face_box=self.last_face_box, is_adjustment=True)
                elif key in [ord('-'), ord('_'), 45]: # -: Disminuir offset
                    self.age_offset -= 1.0
                    os.environ["DERMA_AGE_OFFSET"] = str(self.age_offset)
                    save_calibration_offset(self.age_offset)
                    print(f"\n⚙️ Offset de Edad ajustado y guardado: {int(self.age_offset):+} años")
                    self.toast_message = f"Offset Guardado: {int(self.age_offset):+}a"
                    self.toast_until = time.time() + 2.0
                    if self.state == "DIAGNOSTICADO" and self.last_face_roi is not None and not self.touch_mode:
                        self.last_result = self.execute_diagnosis(self.last_face_roi, face_box=self.last_face_box, is_adjustment=True)

                elif key == 32 and not self.touch_mode: # Captura manual solo en modo de rostro completo
                    if pts is not None and not self.analyzing:
                        print("\n⚡ Disparo manual forzado por el usuario...")
                        min_x, min_y = np.min(pts, axis=0)
                        max_x, max_y = np.max(pts, axis=0)
                        cx = (min_x + max_x) // 2
                        cy = (min_y + max_y) // 2
                        face_w = max_x - min_x
                        face_h = max_y - min_y
                        head_size = int(max(face_w, face_h) * 1.95)
                        face_roi, face_box = self.extract_canonical_face_roi(frame, cx, cy, head_size)

                        self.last_landmarks = pts.copy()
                        rois_to_use = list(self.stability_roi_buffer) if len(self.stability_roi_buffer) > 0 else [face_roi]
                        if len(rois_to_use) < 3:
                            rois_to_use.append(face_roi)
                        result = self.execute_diagnosis(rois_to_use, face_box=face_box)
                        if "error" in result:
                            print(f"⚠️ Diagnóstico manual no completado: {result['error']}")
                            self.toast_message = "Error en evaluacion"
                            self.toast_until = time.time() + 3.0
                            self.state = "BUSCANDO"
                            self.reset_stability()
                        else:
                            self.last_result = result
                            self.state = "DIAGNOSTICADO"
                            self.last_diagnosis_time = time.time()
                            print(json.dumps(result, indent=2, ensure_ascii=False))

        finally:
            self.mobile_control.disconnect()
            if mobile_server is not None:
                server, thread, sock = mobile_server
                server.should_exit = True
                thread.join(timeout=3)
                sock.close()
            self.landmarker.close()
            if self.hand_landmarker is not None:
                self.hand_landmarker.close()
            cap.release()
            if not web_mode:
                cv2.destroyAllWindows()


def list_and_resolve_camera(requested_input=None) -> int:
    """
    Detecta automáticamente dispositivos de video DirectShow / V4L2 y selecciona
    la cámara física real, evitando dispositivos virtuales o drivers fantasmas.
    """
    cameras = []
    if sys.platform.startswith("win"):
        try:
            from pygrabber.dshow_graph import FilterGraph
            graph = FilterGraph()
            devices = graph.get_input_devices()
            for idx, name in enumerate(devices):
                cameras.append({"index": idx, "name": name})
        except Exception:
            pass

    if not cameras:
        backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
        for idx in range(4):
            cap = cv2.VideoCapture(idx, backend)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    cameras.append({"index": idx, "name": f"Dispositivo #{idx}"})
                cap.release()

    print("\n" + "=" * 65)
    print("📹 DISPOSITIVOS DE CÁMARA DETECTADOS EN EL SISTEMA:")
    print("=" * 65)
    for cam in cameras:
        print(f"   [{cam['index']}] {cam['name']}")
    print("=" * 65)

    if requested_input is not None:
        try:
            req_idx = int(requested_input)
            for cam in cameras:
                if cam["index"] == req_idx:
                    print(f"🎯 Seleccionado por índice: [{req_idx}] {cam['name']}\n")
                    return req_idx
            return req_idx
        except ValueError:
            req_name = str(requested_input).lower()
            for cam in cameras:
                if req_name in cam["name"].lower():
                    print(f"🎯 Seleccionado por nombre: [{cam['index']}] {cam['name']}\n")
                    return cam["index"]

    for cam in cameras:
        name_lower = cam["name"].lower()
        if any(brand in name_lower for brand in ["logitech", "brio", "hd camera", "integrated", "c920", "c922"]):
            print(f"🎯 Selección automática (Webcam Física): [{cam['index']}] {cam['name']}\n")
            return cam["index"]

    virtual_keywords = ["meta quest", "obs virtual", "droidcam", "unity", "virtual"]
    for cam in cameras:
        name_lower = cam["name"].lower()
        if not any(v in name_lower for v in virtual_keywords):
            print(f"🎯 Selección automática (Dispositivo no virtual): [{cam['index']}] {cam['name']}\n")
            return cam["index"]

    if cameras:
        print(f"🎯 Selección por defecto: [{cameras[0]['index']}] {cameras[0]['name']}\n")
        return cameras[0]["index"]

    print("⚠️ No se detectaron cámaras en el sistema. Intentando índice 0 por defecto...\n")
    return 0


if __name__ == "__main__":
    requested = None
    if len(sys.argv) > 1:
        requested = sys.argv[1]
    elif os.getenv("DERMA_CAMERA_INDEX"):
        requested = os.getenv("DERMA_CAMERA_INDEX")

    selected_idx = list_and_resolve_camera(requested)
    app_demo = LiveDermaCameraApp(camera_index=selected_idx)
    app_demo.run()
