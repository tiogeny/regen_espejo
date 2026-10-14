"""
Módulo de Informes Clínicos Dermatoscópicos.
Generación de reportes médicos en PDF para Proyecto Derma.
"""

from src.reports.clinical_report_generator import (
    ClinicalReportGenerator,
    generate_clinical_report,
)

__all__ = [
    "ClinicalReportGenerator",
    "generate_clinical_report",
]
