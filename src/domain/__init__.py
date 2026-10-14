"""
Módulo de Dominio Clínico y Motor de Reglas Fitoterapéuticas para Proyecto_derma.
"""
from src.domain.age_stratified_rules import (
    AgeGroup,
    classify_age_group,
    PatientProfile,
    BotanicalCompound,
    ContraindicationIssue,
    PrescriptionResult,
    AgeStratifiedRulesEngine,
    get_clinical_engine,
    THERAPEUTIC_SUBSTITUTIONS,
    modify_patient_profile,
    toggle_patient_profile_flag,
    get_safe_substitution,
    evaluate_with_substitutions,
)
from src.domain.rules_engine import RulesEngine, ClinicalRulesEngine

__all__ = [
    "AgeGroup",
    "classify_age_group",
    "PatientProfile",
    "BotanicalCompound",
    "ContraindicationIssue",
    "PrescriptionResult",
    "AgeStratifiedRulesEngine",
    "get_clinical_engine",
    "THERAPEUTIC_SUBSTITUTIONS",
    "modify_patient_profile",
    "toggle_patient_profile_flag",
    "get_safe_substitution",
    "evaluate_with_substitutions",
    "RulesEngine",
    "ClinicalRulesEngine",
]
