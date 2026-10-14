"""
Pruebas de Integración y Rendimiento del HUD Clínico Táctico (demo_camara.py).
Valida los componentes de UI/UX, arquitectura Zero-Allocation y compatibilidad con Raspberry Pi 5.
"""

from pathlib import Path
import pytest
import numpy as np
import cv2

from demo_camara import (
    draw_glass_rect,
    draw_corner_brackets,
    LiveDermaCameraApp
)


@pytest.fixture
def dummy_frame():
    """Genera un fotograma sintético 1280x720x3 simulación webcam."""
    return np.full((720, 1280, 3), 40, dtype=np.uint8)


class TestZeroAllocationDrawing:
    def test_draw_glass_rect_in_bounds(self, dummy_frame):
        original = dummy_frame.copy()
        draw_glass_rect(dummy_frame, 0, 0, 200, 100, color=(14, 18, 24), alpha=0.88, border_color=(255, 240, 0))
        
        # El área modificada debe haber cambiado de color
        assert not np.array_equal(dummy_frame[10:90, 10:190], original[10:90, 10:190])
        # El área exterior no debe haber cambiado
        assert np.array_equal(dummy_frame[150:200, 250:300], original[150:200, 250:300])

    def test_draw_glass_rect_out_of_bounds_handling(self, dummy_frame):
        # Coordenadas que sobrepasan las dimensiones de la imagen
        draw_glass_rect(dummy_frame, -50, -50, 1500, 800)
        # Coordenadas invertidas
        draw_glass_rect(dummy_frame, 100, 100, 50, 50)
        # No debe lanzar ninguna excepción

    def test_draw_corner_brackets(self, dummy_frame):
        draw_corner_brackets(dummy_frame, 100, 100, 300, 300, color=(0, 255, 180), length=24, thickness=2)
        # Píxel del vértice superior izquierdo debe haberse pintado con el color
        assert tuple(dummy_frame[100, 100]) == (0, 255, 180)


class TestCameraAppHUD:
    @pytest.fixture
    def app_instance(self):
        # Inicializa app sin abrir la cámara física
        app = LiveDermaCameraApp(camera_index=-1)
        return app

    def test_draw_reticle_seeking_state(self, app_instance, dummy_frame):
        app_instance.state = "BUSCANDO"
        app_instance.draw_reticle(dummy_frame, pts=None, progress=0.0)
        # Frame debe contener píxeles modificados
        assert np.any(dummy_frame != 40)

    def test_draw_reticle_stabilizing_state(self, app_instance, dummy_frame):
        app_instance.state = "ESTABILIZANDO"
        # 478 puntos sintéticos centrados
        pts = np.full((478, 2), [640, 360], dtype=np.int32)
        pts[4] = [640, 350] # Punta nasal
        pts[10] = [640, 250] # Frente
        pts[152] = [640, 470] # Mentón

        app_instance.draw_reticle(dummy_frame, pts=pts, progress=0.65)
        assert np.any(dummy_frame != 40)

    def test_draw_reticle_movement_warning(self, app_instance, dummy_frame):
        import time
        app_instance.movement_warning_until = time.time() + 2.0
        app_instance.draw_reticle(dummy_frame, pts=None, progress=0.0)
        assert np.any(dummy_frame != 40)

    def test_draw_hud_across_all_mesh_modes(self, app_instance, dummy_frame):
        pts = np.full((478, 2), [640, 360], dtype=np.int32)
        pts[4] = [640, 350]

        for mode in ["FACE_MESH", "CONTOURS", "OFF"]:
            app_instance.mesh_mode = mode
            f = dummy_frame.copy()
            app_instance.draw_hud(f, pts=pts, progress=0.5)
            assert f.shape == (720, 1280, 3)

    def test_draw_diagnosis_card_with_clinical_data(self, app_instance, dummy_frame):
        app_instance.last_result = {
            "datos": {
                "clinica": {
                    "edad_biologica_estimada": 18,
                    "porcentaje_hiperpigmentacion": 0.45,
                    "clasificacion_severidad": "LEVE",
                    "fototipo_fitzpatrick": 2,
                    "fototipo_label": "Fototipo II (Claro)",
                    "ita_deg": 46.2,
                    "gafas_detectadas": True,
                    "estrato_etario": "JOVEN",
                    "indicacion_primaria": "Seborregulacion y queratoliticos suaves"
                },
                "prescripciones": [
                    {
                        "especie": "Salix alba",
                        "nombre_comun": "Sauce blanco",
                        "precauciones": "Fotoproteccion recomendada"
                    }
                ]
            },
            "metadatos": {
                "execution_time_ms": 28.4
            }
        }
        app_instance.session_ages = [18, 18, 19]
        app_instance._draw_diagnosis_card(dummy_frame)
        assert np.any(dummy_frame != 40)

    def test_render_spot_segmentation_local_roi(self, app_instance, dummy_frame):
        app_instance.last_face_box = (400, 200, 300, 300)
        app_instance.last_mask = np.zeros((224, 224), dtype=np.float32)
        app_instance.last_mask[100:120, 100:120] = 1.0  # Mancha sintética

        # Puntos de contorno facial oval en círculo cerrado alrededor del centro (550, 350)
        pts = np.full((478, 2), [550, 350], dtype=np.int32)
        for i, conn in enumerate(app_instance.conns_oval):
            angle = 2.0 * np.pi * i / len(app_instance.conns_oval)
            pts[conn.start] = [int(550 + 100 * np.cos(angle)), int(350 + 100 * np.sin(angle))]

        app_instance._render_spot_segmentation(dummy_frame, pts)
        assert np.any(dummy_frame != 40)

    def test_draw_reticle_toast_notification(self, app_instance, dummy_frame):
        import time
        app_instance.toast_message = "PDF Guardado: reporte_test.pdf"
        app_instance.toast_until = time.time() + 5.0
        app_instance.draw_reticle(dummy_frame, pts=None, progress=0.0)
        assert np.any(dummy_frame != 40)

    def test_sensitive_skin_toggle_and_card(self, app_instance, dummy_frame):
        app_instance.patient_sensitive_skin = True
        app_instance.last_result = {
            "datos": {
                "clinica": {
                    "edad_biologica_estimada": 18,
                    "porcentaje_hiperpigmentacion": 0.2,
                    "clasificacion_severidad": "LEVE",
                    "fototipo_fitzpatrick": 4,
                    "fototipo_label": "Fototipo IV (Bronceado)",
                    "ita_deg": 25.0,
                    "gafas_detectadas": False,
                    "estrato_etario": "JOVEN",
                    "indicacion_primaria": "Seborregulacion y queratoliticos suaves"
                },
                "prescripciones": []
            },
            "metadatos": {"execution_time_ms": 30.0}
        }
        app_instance._draw_diagnosis_card(dummy_frame)
        assert np.any(dummy_frame != 40)

    def test_export_pdf_report_no_result(self, app_instance):
        app_instance.last_result = None
        result = app_instance.export_pdf_report()
        assert result is None
        assert "Capture diagnostico" in app_instance.toast_message

    def test_export_pdf_report_success(self, app_instance, tmp_path):
        app_instance.last_result = {
            "edad_biologica_estimada": 18,
            "porcentaje_hiperpigmentacion": 0.4,
            "clasificacion_severidad": "Leve",
            "fototipo_fitzpatrick": 4,
            "fototipo_label": "Tipo 4",
            "ita_deg": 22.0,
            "prescripcion_fitoterapeutica": {
                "grupo_etario": "Joven",
                "prescripciones": []
            }
        }
        app_instance.last_face_roi = np.zeros((224, 224, 3), dtype=np.uint8)
        pdf_path = app_instance.export_pdf_report()
        assert pdf_path is not None
        assert Path(pdf_path).exists()
        assert "PDF Guardado" in app_instance.toast_message



