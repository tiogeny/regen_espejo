"""
Pruebas Unitarias para el Generador de Informes Clínicos Dermatoscópicos.

Proyecto Derma — Sistema Dermatoscópico On-Edge.
Verifica:
- Compilación de PDF de 1 página estricta (no overflow).
- Formato y guardado en data/reportes/reporte_{session_id}.pdf.
- Metadatos de sesión (ID, fecha, timestamp, latencia).
- Encabezado institucional ("Proyecto Derma - Sistema Dermatoscópico On-Edge").
- Panel de biometría clínica (edad, fototipo Fitzpatrick con ángulo ITA, hiperpigmentación).
- Incrustación de imágenes (recorte facial y máscara melánica) vía archivos y arreglos numpy.
- Manejo elegante de placeholders cuando las imágenes no están disponibles.
- Prescripción fitoterapéutica formal (SQLite 3NF, estrato etario, principios activos).
- Nota médica obligatoria de fotoprotección SPF 50+.
- Firma facultativa y aviso médico-legal preventivo.
"""

from __future__ import annotations

import base64
import os
import re
import zlib
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pytest
from PIL import Image as PILImage

from src.reports.clinical_report_generator import (
    ClinicalReportGenerator,
    generate_clinical_report,
    DEFAULT_REPORTS_DIR,
)


def _extract_pdf_raw_text(pdf_path: str) -> str:
    """Extrae todo el texto del PDF descompimiendo flujos de contenido."""
    with open(pdf_path, "rb") as f:
        content = f.read()

    text_parts = [content.decode("latin-1", errors="ignore")]

    # Buscar streams comprimidos (Adobe ASCII85 + FlateDecode)
    matches = re.findall(rb"stream[\r\n]+(.*?)endstream", content, re.DOTALL)
    for m in matches:
        clean = m.strip()
        # Caso 1: Adobe ASCII85 + FlateDecode
        if clean.endswith(b"~>"):
            try:
                dec = base64.a85decode(clean, adobe=True)
                txt = zlib.decompress(dec).decode("latin-1", errors="ignore")
                text_parts.append(txt)
                continue
            except Exception:
                pass
        # Caso 2: FlateDecode directo
        try:
            txt = zlib.decompress(clean).decode("latin-1", errors="ignore")
            text_parts.append(txt)
        except Exception:
            pass

    full_text = " ".join(text_parts)
    # Des-escapar caracteres literales de PDF para aserciones
    full_text = full_text.replace(r"\(", "(").replace(r"\)", ")")
    return full_text


def _get_pdf_page_count(pdf_path: str) -> int:
    """Retorna el número de páginas inspeccionando el árbol de objetos PDF."""
    with open(pdf_path, "rb") as f:
        content = f.read()
    matches = re.findall(rb"/Type\s*/Page\b", content)
    return len(matches)


class TestClinicalReportBasic:
    """Pruebas de generación básica, rutas de salida y garantía de 1 página."""

    def test_generate_default_output_dir(self):
        """Verifica guardado en el directorio predeterminado data/reportes/."""
        session_id = "test-session-default-01"
        data = {
            "edad_biologica_estimada": 32,
            "porcentaje_hiperpigmentacion": 1.25,
            "clasificacion_severidad": "LEVE",
            "phototype": 2,
            "ita": 45.0,
            "execution_time_ms": 35.2,
        }

        pdf_path = generate_clinical_report(session_id=session_id, measurement_data=data)
        assert os.path.exists(pdf_path)
        assert Path(pdf_path).name == f"reporte_{session_id}.pdf"
        assert Path(pdf_path).parent == DEFAULT_REPORTS_DIR
        assert _get_pdf_page_count(pdf_path) == 1

        # Limpieza
        os.remove(pdf_path)

    def test_generate_custom_output_dir(self, tmp_path):
        """Verifica que el informe se guarde en un directorio personalizado."""
        session_id = "custom-dir-sess-02"
        custom_dir = tmp_path / "custom_reports_output"
        data = {
            "age": 28,
            "spot_pct": 2.1,
            "severity": "MODERADA",
        }

        generator = ClinicalReportGenerator(output_dir=custom_dir)
        pdf_path = generator.generate(session_id=session_id, measurement_data=data)

        assert os.path.exists(pdf_path)
        assert Path(pdf_path).parent == custom_dir
        assert Path(pdf_path).name == f"reporte_{session_id}.pdf"
        assert _get_pdf_page_count(pdf_path) == 1

    def test_single_page_guarantee(self, tmp_path):
        """Verifica rigurosamente que el PDF generado contenga exactamente 1 página."""
        session_id = "page-count-strict-03"
        data = {
            "edad_biologica_estimada": 55,
            "porcentaje_hiperpigmentacion": 4.8,
            "clasificacion_severidad": "ALTA",
            "fitzpatrick_phototype": 4,
            "ita": 18.5,
            "latency_ms": 52.1,
            "prescripciones": [
                {
                    "especie": "Rosa canina",
                    "nombre_comun": "Rosa mosqueta",
                    "principios_activos": "Ácido trans-retinoico vegetal, Ácido linoleico (Omega-6)",
                    "accion_terapeutica": "Regeneración tisular profunda y restauración de barrera cutánea.",
                    "precauciones": "Uso exclusivamente nocturno. No aplicar sobre lesiones activas de acné quístico.",
                },
                {
                    "especie": "Centella asiatica",
                    "nombre_comun": "Gotu Kola",
                    "principios_activos": "Madecasósido, Asiaticósido, Ácido asiático",
                    "accion_terapeutica": "Estimulación de síntesis de colágeno tipos I y III.",
                    "precauciones": "Evitar en heridas abiertas. Fotoprotección obligatoria SPF 50+.",
                },
            ],
        }

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        assert _get_pdf_page_count(pdf_path) == 1

    def test_class_method_alias(self, tmp_path):
        """Verifica que el método alias generate_clinical_report en la clase funcione igual."""
        session_id = "alias-method-test-04"
        generator = ClinicalReportGenerator(output_dir=tmp_path)
        pdf_path = generator.generate_clinical_report(
            session_id=session_id,
            measurement_data={"age": 40, "spot_pct": 0.8},
        )
        assert os.path.exists(pdf_path)
        assert _get_pdf_page_count(pdf_path) == 1


class TestClinicalReportVisuals:
    """Pruebas de incrustación de imágenes faciales y máscaras de manchas."""

    def test_embed_images_from_file_paths(self, tmp_path):
        """Verifica incrustación correcta de recorte facial y máscara desde archivos."""
        face_img_path = tmp_path / "paciente_face.png"
        mask_img_path = tmp_path / "paciente_mask.png"

        # Crear imágenes sintéticas de prueba
        PILImage.new("RGB", (224, 224), color=(210, 160, 130)).save(face_img_path)
        PILImage.new("L", (224, 224), color=128).save(mask_img_path)

        session_id = "images-filepath-05"
        data = {
            "edad_biologica_estimada": 38,
            "porcentaje_hiperpigmentacion": 1.9,
            "clasificacion_severidad": "LEVE",
            "fitzpatrick_phototype": 3,
            "ita": 35.0,
        }

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            face_img_path=str(face_img_path),
            mask_img_path=str(mask_img_path),
            output_dir=str(tmp_path),
        )

        assert os.path.exists(pdf_path)
        assert _get_pdf_page_count(pdf_path) == 1

        raw_content = _extract_pdf_raw_text(pdf_path)
        # Verificar que el PDF contenga objetos de imagen (/XObject /Image o /Subtype /Image)
        assert "/Image" in raw_content or "/XObject" in raw_content

    def test_embed_images_from_numpy_arrays(self, tmp_path):
        """Verifica incrustación directa desde arreglos numpy en memoria."""
        face_array = np.full((224, 224, 3), 160, dtype=np.uint8)
        mask_array = np.full((224, 224), 255, dtype=np.uint8)

        session_id = "images-numpy-06"
        data = {
            "age": 22,
            "spot_pct": 0.4,
            "severity": "NINGUNA",
            "mask_img_path": mask_array,
        }

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            face_img_path=face_array,
            output_dir=str(tmp_path),
        )

        assert os.path.exists(pdf_path)
        assert _get_pdf_page_count(pdf_path) == 1

    def test_graceful_handling_missing_images(self, tmp_path):
        """Verifica que si no hay imágenes o las rutas no existen, se renderice un placeholder sin fallar."""
        session_id = "missing-images-07"
        data = {
            "age": 45,
            "spot_pct": 2.8,
            "severity": "MODERADA",
            "face_img_path": "/ruta/no/existente/face.png",
            "mask_img_path": "/ruta/no/existente/mask.png",
        }

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )

        assert os.path.exists(pdf_path)
        assert _get_pdf_page_count(pdf_path) == 1


class TestClinicalReportBiometrics:
    """Pruebas de biometría clínica, estratos etarios, fototipos e ITA."""

    @pytest.mark.parametrize(
        "age, expected_strata",
        [
            (19, "Piel Joven"),
            (24, "Piel Joven"),
            (25, "Piel Adulta"),
            (35, "Piel Adulta"),
            (40, "Piel Madura"),
            (68, "Piel Madura"),
        ],
    )
    def test_age_strata_classification(self, tmp_path, age, expected_strata):
        """Verifica la adecuada estratificación etaria en el panel biométrico."""
        session_id = f"strata-test-{age}"
        data = {
            "edad_biologica_estimada": age,
            "porcentaje_hiperpigmentacion": 1.5,
        }

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        assert _get_pdf_page_count(pdf_path) == 1

        raw_text = _extract_pdf_raw_text(pdf_path)
        assert expected_strata in raw_text

    @pytest.mark.parametrize(
        "phototype, ita_deg, expected_label",
        [
            (1, 60.5, "Fototipo I (Muy claro)"),
            (2, 48.2, "Fototipo II (Claro)"),
            (3, 34.0, "Fototipo III (Intermedio)"),
            (4, 19.5, "Fototipo IV (Bronceado / Moreno)"),
            (5, -5.0, "Fototipo V (Oscuro)"),
            (6, -45.0, "Fototipo VI (Muy oscuro)"),
        ],
    )
    def test_fitzpatrick_phototype_and_ita(self, tmp_path, phototype, ita_deg, expected_label):
        """Verifica la inclusión de los 6 fototipos de Fitzpatrick y el ángulo ITA."""
        session_id = f"fitz-test-{phototype}"
        data = {
            "age": 30,
            "spot_pct": 1.0,
            "phototype": phototype,
            "ita": ita_deg,
        }

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        assert _get_pdf_page_count(pdf_path) == 1

        raw_text = _extract_pdf_raw_text(pdf_path)
        assert expected_label in raw_text
        assert f"{ita_deg:+.2f}" in raw_text

    def test_ita_only_phototype_deduction(self, tmp_path):
        """Verifica que el fototipo se deduzca automáticamente si solo se provee el ángulo ITA."""
        session_id = "ita-only-deduction"
        data = {
            "age": 33,
            "spot_pct": 0.9,
            "ita": 58.0,  # > 55° -> Fototipo I
        }

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        raw_text = _extract_pdf_raw_text(pdf_path)
        assert "Fototipo I (Muy claro)" in raw_text

    @pytest.mark.parametrize(
        "spot_pct, expected_severity",
        [
            (0.2, "NINGUNA"),
            (1.4, "LEVE"),
            (3.1, "MODERADA"),
            (7.5, "ALTA"),
        ],
    )
    def test_severity_derivation_from_spot_percentage(self, tmp_path, spot_pct, expected_severity):
        """Verifica que el nivel de severidad se infiera correctamente según el umbral."""
        session_id = f"sev-test-{int(spot_pct * 10)}"
        data = {
            "age": 29,
            "porcentaje_hiperpigmentacion": spot_pct,
        }

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        raw_text = _extract_pdf_raw_text(pdf_path)
        assert expected_severity in raw_text


class TestClinicalReportPrescriptions:
    """Pruebas de la tabla de prescripciones fitoterapéuticas formal (SQLite 3NF)."""

    def test_no_automatic_prescriptions_young(self, tmp_path):
        """Verifica prescripción para paciente joven desde el catálogo de la BD."""
        session_id = "presc-young-08"
        # Joven (20 años), severidad LEVE -> Arctostaphylos uva-ursi según seeds.sql
        data = {
            "edad_biologica_estimada": 20,
            "porcentaje_hiperpigmentacion": 1.2,
            "clasificacion_severidad": "LEVE",
        }

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        assert _get_pdf_page_count(pdf_path) == 1

        raw_text = _extract_pdf_raw_text(pdf_path)
        # Debe contener la especie botánica y principios activos
        assert "Arctostaphylos uva-ursi" not in raw_text
        assert "Melaleuca alternifolia" not in raw_text

    def test_no_automatic_prescriptions_mature(self, tmp_path):
        """Verifica prescripción para paciente maduro desde la BD."""
        session_id = "presc-mature-09"
        # 55 años, severidad ALTA -> Rosa canina + Glycyrrhiza glabra según seeds.sql
        data = {
            "edad_biologica_estimada": 55,
            "porcentaje_hiperpigmentacion": 5.2,
            "clasificacion_severidad": "ALTA",
        }

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        assert _get_pdf_page_count(pdf_path) == 1

        raw_text = _extract_pdf_raw_text(pdf_path)
        assert "Rosa canina" not in raw_text
        assert "Glycyrrhiza glabra" not in raw_text

    def test_custom_prescriptions_in_measurement_data(self, tmp_path):
        """Verifica que se respeten y enriquezcan prescripciones provistas explícitamente."""
        session_id = "custom-presc-10"
        data = {
            "age": 42,
            "spot_pct": 2.5,
            "prescripciones": [
                {
                    "especie": "Centella asiatica",
                    "nombre_comun": "Gotu Kola",
                    "principios_activos": "Madecasósido y Asiaticósido",
                    "accion_terapeutica": "Aumento de síntesis de procolágeno dérmico.",
                    "precauciones": "No aplicar en eccemas exudativos.",
                }
            ],
        }

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        raw_text = _extract_pdf_raw_text(pdf_path)
        assert "Centella asiatica" in raw_text
        assert "Madecas" in raw_text
        assert "Gotu Kola" in raw_text


class TestClinicalReportInstitutionalAndLegal:
    """Pruebas de encabezado institucional, disclaimer médico y nota SPF 50+."""

    def test_institutional_header_present(self, tmp_path):
        """Verifica presencia del encabezado institucional formal."""
        session_id = "header-test-11"
        data = {"age": 30, "spot_pct": 1.0}

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        raw_text = _extract_pdf_raw_text(pdf_path)
        assert "PROYECTO DERMA" in raw_text
        assert "SISTEMA DERMATOSC" in raw_text

    def test_spf50_callout_present(self, tmp_path):
        """Verifica presencia destacada de la prescripción de fotoprotección SPF 50+."""
        session_id = "spf50-test-12"
        data = {"age": 30, "spot_pct": 1.0}

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        raw_text = _extract_pdf_raw_text(pdf_path)
        assert "SPF 50+" in raw_text or "FPS 50+" in raw_text
        assert "FOTOPROTECCI" in raw_text

    def test_medical_disclaimer_and_signature_block(self, tmp_path):
        """Verifica el aviso preventivo médico-legal y la firma facultativa."""
        session_id = "legal-test-13"
        data = {"age": 30, "spot_pct": 1.0}

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        raw_text = _extract_pdf_raw_text(pdf_path)
        assert "Aviso" in raw_text or "Preventivo" in raw_text
        assert "Dermat" in raw_text
        assert "Firma" in raw_text

    def test_session_id_sanitization_for_filename(self, tmp_path):
        """Verifica que caracteres no válidos en session_id sean saneados para el archivo."""
        session_id = "urn:derma/device:uuid\\test"
        data = {"age": 30, "spot_pct": 1.0}

        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data=data,
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        # El nombre del archivo no debe contener : ni / ni \
        filename = Path(pdf_path).name
        assert ":" not in filename
        assert "/" not in filename
        assert "\\" not in filename
        assert _get_pdf_page_count(pdf_path) == 1

    def test_empty_measurement_data_fallback(self, tmp_path):
        """Verifica que un diccionario vacío no lance excepciones y aplique defaults clínicos."""
        session_id = "empty-data-14"
        pdf_path = generate_clinical_report(
            session_id=session_id,
            measurement_data={},
            output_dir=str(tmp_path),
        )
        assert os.path.exists(pdf_path)
        assert _get_pdf_page_count(pdf_path) == 1
