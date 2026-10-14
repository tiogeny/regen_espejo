"""
Motor de Reglas Clínicas de Fitoterapia Estratificada por Edad y Contraindicaciones Médicas.

Proyecto_derma - Sistema de Diagnóstico Dermatoscópico y Recomendación Fitoterapéutica.
Estratificación etaria:
  - Piel Joven (edad < 25): Seborregulación y queratolíticos suaves
    (Melaleuca alternifolia, Salix alba).
  - Piel Adulta (25 <= edad < 40): Inhibición de tirosinasa y tono
    (Arctostaphylos uva-ursi, Glycyrrhiza glabra).
  - Piel Madura (edad >= 40): Síntesis de colágeno y antioxidantes celulares
    (Centella asiatica, Camellia sinensis).

Incluye motor de validación toxicológica y farmacológica de contraindicaciones
(salicilatos en piel sensible, restricciones en embarazo y lactancia, y alergias conocidas).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple


class AgeGroup(str, Enum):
    """Grupos etarios clínicos para prescripción fitoterapéutica."""
    JOVEN = "JOVEN"      # edad < 25 años
    ADULTO = "ADULTO"    # 25 <= edad < 40 años
    MADURO = "MADURO"    # edad >= 40 años


def classify_age_group(age: int) -> AgeGroup:
    """
    Clasifica la edad biológica en el grupo etario correspondiente.

    Args:
        age: Edad en años cumplidos (0 - 120).

    Returns:
        AgeGroup: JOVEN (<25), ADULTO (25-39), MADURO (>=40).

    Raises:
        ValueError: Si la edad está fuera del rango fisiológico admisible.
    """
    if age < 0 or age > 120:
        raise ValueError(f"Edad ({age}) fuera del rango fisiológico válido (0 a 120 años).")
    if age < 25:
        return AgeGroup.JOVEN
    elif age < 40:
        return AgeGroup.ADULTO
    else:
        return AgeGroup.MADURO


@dataclass
class PatientProfile:
    """
    Perfil clínico dermatológico del paciente para evaluación de seguridad farmacológica.
    Soporta argumentos y propiedades en inglés y español indistintamente.
    """
    age: int
    sensitive_skin: bool = False
    salicylate_allergy: bool = False
    is_pregnant: bool = False
    is_lactating: bool = False
    known_allergies: List[str] = field(default_factory=list)
    has_open_wounds: bool = False
    has_cystic_acne: bool = False
    fitzpatrick_phototype: Optional[int] = None
    hyperpigmentation_pct: Optional[float] = None
    severity: Optional[str] = None

    def __init__(
        self,
        age: Optional[int] = None,
        edad: Optional[int] = None,
        sensitive_skin: Optional[bool] = None,
        piel_sensible: Optional[bool] = None,
        salicylate_allergy: Optional[bool] = None,
        alergia_salicilatos: Optional[bool] = None,
        is_pregnant: Optional[bool] = None,
        embarazo: Optional[bool] = None,
        is_lactating: Optional[bool] = None,
        lactancia: Optional[bool] = None,
        known_allergies: Optional[List[str]] = None,
        alergias_conocidas: Optional[List[str]] = None,
        has_open_wounds: Optional[bool] = None,
        heridas_abiertas: Optional[bool] = None,
        has_cystic_acne: Optional[bool] = None,
        acne_quistico: Optional[bool] = None,
        fitzpatrick_phototype: Optional[int] = None,
        fototipo: Optional[int] = None,
        hyperpigmentation_pct: Optional[float] = None,
        porcentaje_manchas: Optional[float] = None,
        severity: Optional[str] = None,
        severidad: Optional[str] = None,
    ):
        target_age = age if age is not None else edad
        if target_age is None:
            raise ValueError("El parámetro de edad ('age' o 'edad') es obligatorio.")
        self.age = int(target_age)

        self.sensitive_skin = bool(
            sensitive_skin if sensitive_skin is not None else (piel_sensible or False)
        )
        self.salicylate_allergy = bool(
            salicylate_allergy if salicylate_allergy is not None else (alergia_salicilatos or False)
        )
        self.is_pregnant = bool(
            is_pregnant if is_pregnant is not None else (embarazo or False)
        )
        self.is_lactating = bool(
            is_lactating if is_lactating is not None else (lactancia or False)
        )

        allergies: List[str] = []
        if known_allergies:
            allergies.extend(known_allergies)
        if alergias_conocidas:
            allergies.extend(alergias_conocidas)
        self.known_allergies = [a.strip().lower() for a in allergies if isinstance(a, str)]

        self.has_open_wounds = bool(
            has_open_wounds if has_open_wounds is not None else (heridas_abiertas or False)
        )
        self.has_cystic_acne = bool(
            has_cystic_acne if has_cystic_acne is not None else (acne_quistico or False)
        )
        self.fitzpatrick_phototype = fitzpatrick_phototype or fototipo
        self.hyperpigmentation_pct = (
            hyperpigmentation_pct if hyperpigmentation_pct is not None else porcentaje_manchas
        )
        self.severity = severity or severidad

    # Propiedades alias en español
    @property
    def edad(self) -> int:
        return self.age

    @property
    def piel_sensible(self) -> bool:
        return self.sensitive_skin

    @property
    def alergia_salicilatos(self) -> bool:
        return self.salicylate_allergy

    @property
    def embarazo(self) -> bool:
        return self.is_pregnant

    @property
    def lactancia(self) -> bool:
        return self.is_lactating

    @property
    def alergias(self) -> List[str]:
        return self.known_allergies

    @property
    def heridas_abiertas(self) -> bool:
        return self.has_open_wounds

    @property
    def acne_quistico(self) -> bool:
        return self.has_cystic_acne

    @property
    def severidad(self) -> Optional[str]:
        return self.severity

    # -------------------------------------------------------------------------
    # Modificadores interactivos de banderas clínicas de seguridad
    # -------------------------------------------------------------------------
    def toggle_sensitive_skin(self, state: Optional[bool] = None) -> bool:
        """
        Alterna o establece la bandera de piel sensible o reactiva.
        Si state es None, invierte el valor actual. Retorna el nuevo estado.
        """
        self.sensitive_skin = not self.sensitive_skin if state is None else bool(state)
        return self.sensitive_skin

    def toggle_pregnancy(self, state: Optional[bool] = None) -> bool:
        """
        Alterna o establece la bandera de gestación / embarazo.
        Si state es None, invierte el valor actual. Retorna el nuevo estado.
        """
        self.is_pregnant = not self.is_pregnant if state is None else bool(state)
        return self.is_pregnant

    def toggle_salicylate_allergy(self, state: Optional[bool] = None) -> bool:
        """Alterna o establece la bandera de alergia diagnosticada a salicilatos."""
        self.salicylate_allergy = not self.salicylate_allergy if state is None else bool(state)
        return self.salicylate_allergy

    def toggle_lactation(self, state: Optional[bool] = None) -> bool:
        """Alterna o establece la bandera de periodo de lactancia materna activa."""
        self.is_lactating = not self.is_lactating if state is None else bool(state)
        return self.is_lactating

    def toggle_cystic_acne(self, state: Optional[bool] = None) -> bool:
        """Alterna o establece la bandera de presencia de acné quístico activo."""
        self.has_cystic_acne = not self.has_cystic_acne if state is None else bool(state)
        return self.has_cystic_acne

    def toggle_open_wounds(self, state: Optional[bool] = None) -> bool:
        """Alterna o establece la bandera de presencia de heridas abiertas o eccemas exudativos."""
        self.has_open_wounds = not self.has_open_wounds if state is None else bool(state)
        return self.has_open_wounds

    def toggle_flag(self, flag_name: str, state: Optional[bool] = None) -> bool:
        """
        Alterna de forma interactiva y dinámica cualquier bandera clínica del paciente
        soportando identificadores tanto en inglés como en español.
        """
        key = flag_name.strip().lower()
        if key in ("sensitive_skin", "piel_sensible"):
            return self.toggle_sensitive_skin(state)
        elif key in ("is_pregnant", "pregnant", "embarazo", "embarazada"):
            return self.toggle_pregnancy(state)
        elif key in ("salicylate_allergy", "alergia_salicilatos", "salicilatos"):
            return self.toggle_salicylate_allergy(state)
        elif key in ("is_lactating", "lactating", "lactancia", "lactante"):
            return self.toggle_lactation(state)
        elif key in ("has_cystic_acne", "cystic_acne", "acne_quistico", "acné_quístico"):
            return self.toggle_cystic_acne(state)
        elif key in ("has_open_wounds", "open_wounds", "heridas_abiertas", "heridas"):
            return self.toggle_open_wounds(state)
        else:
            raise KeyError(f"Bandera clínica no reconocida: '{flag_name}'.")

    def set_flag(self, flag_name: str, value: bool) -> PatientProfile:
        """Establece una bandera clínica y retorna self para permitir encadenamiento fluido."""
        self.toggle_flag(flag_name, state=value)
        return self

    def set_sensitive_skin(self, enabled: bool = True) -> PatientProfile:
        """Configura explícitamente piel sensible. Retorna self."""
        self.sensitive_skin = bool(enabled)
        return self

    def set_pregnant(self, enabled: bool = True) -> PatientProfile:
        """Configura explícitamente estado de embarazo. Retorna self."""
        self.is_pregnant = bool(enabled)
        return self

    def set_salicylate_allergy(self, enabled: bool = True) -> PatientProfile:
        """Configura explícitamente alergia a salicilatos. Retorna self."""
        self.salicylate_allergy = bool(enabled)
        return self

    def set_lactating(self, enabled: bool = True) -> PatientProfile:
        """Configura explícitamente lactancia. Retorna self."""
        self.is_lactating = bool(enabled)
        return self

    def set_cystic_acne(self, enabled: bool = True) -> PatientProfile:
        """Configura explícitamente acné quístico. Retorna self."""
        self.has_cystic_acne = bool(enabled)
        return self

    def set_open_wounds(self, enabled: bool = True) -> PatientProfile:
        """Configura explícitamente heridas abiertas. Retorna self."""
        self.has_open_wounds = bool(enabled)
        return self

    def update_flags(self, **flags) -> PatientProfile:
        """
        Actualiza múltiples banderas clínicas de forma interactiva.
        Soporta argumentos en inglés y español. Retorna self.
        """
        for flag_name, val in flags.items():
            self.set_flag(flag_name, bool(val))
        return self

    def add_allergy(self, allergy: str) -> PatientProfile:
        """Añade una alergia conocida al perfil clínico del paciente."""
        cleaned = allergy.strip().lower()
        if cleaned and cleaned not in self.known_allergies:
            self.known_allergies.append(cleaned)
        return self

    def remove_allergy(self, allergy: str) -> PatientProfile:
        """Elimina una alergia conocida del perfil clínico del paciente."""
        cleaned = allergy.strip().lower()
        self.known_allergies = [a for a in self.known_allergies if a != cleaned]
        return self

    # Aliases en español para paridad clínica total
    def alternar_piel_sensible(self, state: Optional[bool] = None) -> bool:
        return self.toggle_sensitive_skin(state)

    def alternar_embarazo(self, state: Optional[bool] = None) -> bool:
        return self.toggle_pregnancy(state)

    def alternar_acne_quistico(self, state: Optional[bool] = None) -> bool:
        return self.toggle_cystic_acne(state)

    def alternar_lactancia(self, state: Optional[bool] = None) -> bool:
        return self.toggle_lactation(state)

    def alternar_alergia_salicilatos(self, state: Optional[bool] = None) -> bool:
        return self.toggle_salicylate_allergy(state)

    def alternar_heridas_abiertas(self, state: Optional[bool] = None) -> bool:
        return self.toggle_open_wounds(state)

    def alternar_bandera(self, flag_name: str, state: Optional[bool] = None) -> bool:
        return self.toggle_flag(flag_name, state)

    def actualizar_banderas(self, **flags) -> PatientProfile:
        return self.update_flags(**flags)



@dataclass(frozen=True)
class BotanicalCompound:
    """Entidad clínica de principio activo botánico."""
    scientific_name: str
    common_name: str
    active_compounds: Tuple[str, ...]
    therapeutic_action: str
    clinical_indication: str
    precautions: str
    target_age_groups: Tuple[AgeGroup, ...]

    @property
    def especie(self) -> str:
        return self.scientific_name

    @property
    def nombre_comun(self) -> str:
        return self.common_name

    @property
    def principios_activos(self) -> List[str]:
        return list(self.active_compounds)

    @property
    def precauciones(self) -> str:
        return self.precautions

    @property
    def accion_terapeutica(self) -> str:
        return self.therapeutic_action

    @property
    def indicacion_clinica(self) -> str:
        return self.clinical_indication

    def to_dict(self) -> Dict[str, Any]:
        return {
            "especie": self.scientific_name,
            "nombre_comun": self.common_name,
            "principios_activos": list(self.active_compounds),
            "accion_terapeutica": self.therapeutic_action,
            "indicacion_clinica": self.clinical_indication,
            "precauciones": self.precautions,
            "grupos_etarios": [g.value for g in self.target_age_groups],
        }


@dataclass
class ContraindicationIssue:
    """Descripción detallada de una contraindicación o advertencia de seguridad."""
    species: str
    common_name: str
    category: str  # SENSITIVE_SKIN, SALICYLATE_ALLERGY, PREGNANCY, LACTATION, ALLERGY, CLINICAL_RESTRICTION
    severity: str  # ABSOLUTE, RELATIVE, PRECAUTION
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "especie": self.species,
            "nombre_comun": self.common_name,
            "categoria": self.category,
            "severidad": self.severity,
            "motivo": self.reason,
        }


@dataclass
class PrescriptionResult:
    """Resultado del triaje fitoterapéutico evaluado y filtrado por seguridad."""
    profile: PatientProfile
    age_group: AgeGroup
    primary_indication: str
    approved_prescriptions: List[BotanicalCompound]
    contraindicated_prescriptions: Dict[str, List[ContraindicationIssue]] = field(default_factory=dict)
    clinical_warnings: List[str] = field(default_factory=list)
    substitutions: Dict[str, BotanicalCompound] = field(default_factory=dict)

    @property
    def prescripciones_aprobadas(self) -> List[BotanicalCompound]:
        return self.approved_prescriptions

    @property
    def prescripciones_contraindicadas(self) -> Dict[str, List[ContraindicationIssue]]:
        return self.contraindicated_prescriptions

    @property
    def sustituciones(self) -> Dict[str, BotanicalCompound]:
        return self.substitutions

    @property
    def substituted_species(self) -> Dict[str, str]:
        """Diccionario mapeando {especie_contraindicada: especie_sustituta}."""
        return {contra: comp.scientific_name for contra, comp in self.substitutions.items()}

    @property
    def has_substitutions(self) -> bool:
        return len(self.substitutions) > 0

    @property
    def grupo_etario(self) -> AgeGroup:
        return self.age_group

    @property
    def indicacion_primaria(self) -> str:
        return self.primary_indication

    @property
    def approved_species(self) -> List[str]:
        return [c.scientific_name for c in self.approved_prescriptions]

    @property
    def contraindicated_species(self) -> List[str]:
        return list(self.contraindicated_prescriptions.keys())

    @property
    def has_contraindications(self) -> bool:
        return len(self.contraindicated_prescriptions) > 0

    @property
    def is_completely_contraindicated(self) -> bool:
        return len(self.approved_prescriptions) == 0

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "edad": self.profile.age,
            "grupo_etario": self.age_group.value,
            "indicacion_primaria": self.primary_indication,
            "prescripciones_aprobadas": [c.to_dict() for c in self.approved_prescriptions],
            "prescripciones_contraindicadas": {
                spec: [iss.to_dict() for iss in issues]
                for spec, issues in self.contraindicated_prescriptions.items()
            },
            "advertencias_clinicas": self.clinical_warnings,
        }
        if self.substitutions:
            data["sustituciones"] = {
                spec: sub.to_dict() for spec, sub in self.substitutions.items()
            }
        return data


# ============================================================================
# Catálogo Clínico Farmacológico de Especies Botánicas Estratificadas
# ============================================================================

MELALEUCA_ALTERNIFOLIA = BotanicalCompound(
    scientific_name="Melaleuca alternifolia",
    common_name="Árbol del té",
    active_compounds=("Terpinen-4-ol", "gamma-terpineno", "alfa-terpineol"),
    therapeutic_action="Seborregulación, antimicrobiano contra Cutibacterium acnes y control de micro-comedones.",
    clinical_indication="Seborregulación y queratolíticos suaves",
    precautions="Uso exclusivamente tópico en formulaciones cosmecéuticas diluidas (2-5%). No ingerir bajo ninguna circunstancia.",
    target_age_groups=(AgeGroup.JOVEN,),
)

SALIX_ALBA = BotanicalCompound(
    scientific_name="Salix alba",
    common_name="Sauce blanco",
    active_compounds=("Salicina", "Ácido salicílico vegetal"),
    therapeutic_action="Queratolítico suave, desobstrucción folicular, acción comedolítica y antiinflamatoria dérmica.",
    clinical_indication="Seborregulación y queratolíticos suaves",
    precautions="Uso conjunto con fotoprotección SPF 50+. Evitar combinar simultáneamente con exfoliantes mecánicos agresivos o peróxidos.",
    target_age_groups=(AgeGroup.JOVEN,),
)

ARCTOSTAPHYLOS_UVA_URSI = BotanicalCompound(
    scientific_name="Arctostaphylos uva-ursi",
    common_name="Gayuba",
    active_compounds=("Arbutina", "Metilarbutina"),
    therapeutic_action="Inhibición competitiva y reversible de la enzima tirosinasa, reducción de síntesis melánica y homogeneización del tono.",
    clinical_indication="Inhibición de tirosinasa y tono",
    precautions="No combinar simultáneamente con peróxido de benzoilo ni hidroquinona sintética. Uso preferentemente nocturno y con fotoprotección diurna SPF 50+.",
    target_age_groups=(AgeGroup.ADULTO,),
)

GLYCYRRHIZA_GLABRA = BotanicalCompound(
    scientific_name="Glycyrrhiza glabra",
    common_name="Regaliz",
    active_compounds=("Glabridina", "Licochalcona A", "Ácido glicirrícico"),
    therapeutic_action="Despigmentante por dispersión de melanina e inhibición enzimática suave, con potente efecto calmante y antioxidante dérmico.",
    clinical_indication="Inhibición de tirosinasa y tono",
    precautions="Desaconsejado en pacientes con hipersensibilidad a flavonoides o dermatitis perioral aguda.",
    target_age_groups=(AgeGroup.ADULTO,),
)

CENTELLA_ASIATICA = BotanicalCompound(
    scientific_name="Centella asiatica",
    common_name="Gotu Kola",
    active_compounds=("Madecasósido", "Asiaticósido", "Ácido asiático", "Ácido madecásico"),
    therapeutic_action="Estimulación de la síntesis de colágeno tipos I y III en fibroblastos dérmicos, aumento de firmeza y regeneración de la matriz extracelular.",
    clinical_indication="Síntesis de colágeno y antioxidantes celulares",
    precautions="Evitar en heridas abiertas no epitelizadas o eccemas exudativos. Posible sensibilización tópica rara en pieles hipereactivas.",
    target_age_groups=(AgeGroup.MADURO,),
)

CAMELLIA_SINENSIS = BotanicalCompound(
    scientific_name="Camellia sinensis",
    common_name="Té verde",
    active_compounds=("Epigalocatequina galato (EGCG)", "Polifenoles catequínicos"),
    therapeutic_action="Antioxidación celular profunda, neutralización de especies reactivas de oxígeno (ROS) e inhibición de metaloproteinasas (MMP-1).",
    clinical_indication="Síntesis de colágeno y antioxidantes celulares",
    precautions="Puede provocar ligera sensación de tirantez o sequedad en cutis alípicos si se emplea en concentraciones superiores al 5%.",
    target_age_groups=(AgeGroup.MADURO,),
)

ROSA_CANINA = BotanicalCompound(
    scientific_name="Rosa canina",
    common_name="Rosa mosqueta",
    active_compounds=("Ácido trans-retinoico vegetal", "Ácido linoleico (Omega-6)", "Ácido alfa-linolénico (Omega-3)"),
    therapeutic_action="Regeneración tisular profunda, restauración de la barrera hidrolipídica y atenuación de cicatrices y fotoenvejecimiento avanzado.",
    clinical_indication="Síntesis de colágeno y antioxidantes celulares",
    precautions="Fotosensibilidad en pieles reactivas; uso exclusivamente nocturno. No aplicar sobre lesiones activas de acné quístico.",
    target_age_groups=(AgeGroup.MADURO,),
)

BOTANICAL_CATALOG: Dict[str, BotanicalCompound] = {
    "Melaleuca alternifolia": MELALEUCA_ALTERNIFOLIA,
    "Salix alba": SALIX_ALBA,
    "Arctostaphylos uva-ursi": ARCTOSTAPHYLOS_UVA_URSI,
    "Glycyrrhiza glabra": GLYCYRRHIZA_GLABRA,
    "Centella asiatica": CENTELLA_ASIATICA,
    "Camellia sinensis": CAMELLIA_SINENSIS,
    "Rosa canina": ROSA_CANINA,
}

# ----------------------------------------------------------------------------
# Catálogo de Sustituciones Terapéuticas Seguras (Evitar activos contraindicados)
# ----------------------------------------------------------------------------
# Jerarquía farmacológica de reemplazos ante patologías, hipersensibilidad o estados fisiológicos.
THERAPEUTIC_SUBSTITUTIONS: Dict[str, Tuple[BotanicalCompound, ...]] = {
    # Salix alba (Sauce blanco - Queratolítico / Salicilatos):
    # Contraindicado en piel sensible, alergia a salicilatos o embarazo/lactancia.
    # Sustituto de 1ra línea: Melaleuca alternifolia (Seborregulador no queratolítico suave).
    # Sustituto de 2da línea: Camellia sinensis (Calmante y antioxidante no irritante).
    "Salix alba": (MELALEUCA_ALTERNIFOLIA, CAMELLIA_SINENSIS),

    # Melaleuca alternifolia (Árbol del té - Terpenos):
    # Contraindicado en hipersensibilidad o alergia a terpenos.
    # Alternativas: Camellia sinensis o Salix alba (si no hay piel sensible).
    "Melaleuca alternifolia": (CAMELLIA_SINENSIS, SALIX_ALBA),

    # Arctostaphylos uva-ursi (Gayuba - Arbutina/Hidroquinona):
    # Contraindicado en embarazo y lactancia (riesgo de toxicidad por hidroquinona).
    # Sustituto 1: Glycyrrhiza glabra (si no hay embarazo).
    # Sustituto 2: Camellia sinensis o Centella asiatica (antioxidantes y unificadores seguros).
    "Arctostaphylos uva-ursi": (GLYCYRRHIZA_GLABRA, CAMELLIA_SINENSIS, CENTELLA_ASIATICA),

    # Glycyrrhiza glabra (Regaliz - Glabridina/Ácido glicirrícico):
    # Contraindicado en embarazo (fitoestrógenos / cortisol fetal) o alergia a flavonoides.
    # Sustitutos seguros: Camellia sinensis y Centella asiatica.
    "Glycyrrhiza glabra": (CAMELLIA_SINENSIS, CENTELLA_ASIATICA),

    # Centella asiatica (Gotu Kola - Triterpenos):
    # Contraindicado en heridas abiertas no epitelizadas o alergia apiaceae.
    # Sustituto seguro: Camellia sinensis (modulador dérmico antioxidante no proliferativo de tejido de granulación).
    "Centella asiatica": (CAMELLIA_SINENSIS,),

    # Camellia sinensis (Té verde - EGCG):
    # En hipersensibilidad alérgica infrecuente.
    # Sustituto seguro: Centella asiatica (siempre que la piel esté intacta).
    "Camellia sinensis": (CENTELLA_ASIATICA,),

    # Rosa canina (Rosa mosqueta - Fracción lipídica / retinol vegetal):
    # Contraindicado en lesiones activas de acné quístico (comedogénico).
    # Sustitutos seguros: Centella asiatica y Camellia sinensis (no comedogénicos, antiinflamatorios).
    "Rosa canina": (CENTELLA_ASIATICA, CAMELLIA_SINENSIS),
}


# ============================================================================
# Motor de Reglas Clínicas Estratificadas y Contraindicaciones
# ============================================================================

class AgeStratifiedRulesEngine:
    """
    Motor clínico determinista para la selección fitoterapéutica según estrato etario
    y verificación rigurosa de contraindicaciones médicas y farmacológicas.
    """

    def __init__(self):
        self._strata_compounds: Dict[AgeGroup, List[BotanicalCompound]] = {
            AgeGroup.JOVEN: [MELALEUCA_ALTERNIFOLIA, SALIX_ALBA],
            AgeGroup.ADULTO: [ARCTOSTAPHYLOS_UVA_URSI, GLYCYRRHIZA_GLABRA],
            AgeGroup.MADURO: [CENTELLA_ASIATICA, CAMELLIA_SINENSIS],
        }

        self._strata_indications: Dict[AgeGroup, str] = {
            AgeGroup.JOVEN: "Seborregulación y queratolíticos suaves",
            AgeGroup.ADULTO: "Inhibición de tirosinasa y tono",
            AgeGroup.MADURO: "Síntesis de colágeno y antioxidantes celulares",
        }

    def get_age_group(self, age: int) -> AgeGroup:
        """Determina el estrato etario a partir de la edad cronológica o biológica."""
        return classify_age_group(age)

    def get_primary_indication(self, age_group: AgeGroup) -> str:
        """Obtiene la condición primaria / indicación terapéutica del estrato."""
        return self._strata_indications[age_group]

    def get_candidate_compounds(self, age_group: AgeGroup) -> List[BotanicalCompound]:
        """Retorna los principios activos botánicos candidatos para el estrato de edad."""
        return list(self._strata_compounds[age_group])

    def check_contraindications(
        self,
        compound: BotanicalCompound,
        profile: PatientProfile,
    ) -> List[ContraindicationIssue]:
        """
        Verifica exhaustivamente las contraindicaciones farmacológicas y clínicas
        de un principio activo botánico específico frente al perfil del paciente.
        """
        issues: List[ContraindicationIssue] = []
        name = compound.scientific_name
        common = compound.common_name

        # Normalizar lista de alergias para búsqueda de patrones
        allergies = [a.lower() for a in profile.known_allergies]

        # ---------------------------------------------------------------------
        # 1. Salix alba (Sauce blanco - Salicilatos / Salicina)
        # ---------------------------------------------------------------------
        if name == "Salix alba":
            # A) Piel sensible o reactiva
            if profile.sensitive_skin:
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="SENSITIVE_SKIN",
                        severity="ABSOLUTE",
                        reason=(
                            "Contraindicado en piel sensible o reactiva: los salicilatos / salicina "
                            "inducen disrupción de la barrera cutánea frágil, eritema persistente "
                            "y exfoliación excesiva."
                        ),
                    )
                )

            # B) Alergia a salicilatos o ácido acetilsalicílico
            salicylate_allergy_detected = profile.salicylate_allergy or any(
                term in a
                for a in allergies
                for term in ("salicil", "aspirin", "acetilsalicilico", "acido acetilsalicilico")
            )
            if salicylate_allergy_detected:
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="SALICYLATE_ALLERGY",
                        severity="ABSOLUTE",
                        reason=(
                            "Contraindicación médica absoluta: hipersensibilidad alérgica diagnosticada "
                            "a salicilatos o ácido acetilsalicílico (riesgo de anafilaxia o angioedema)."
                        ),
                    )
                )

            # C) Embarazo (absorción de salicilatos)
            if profile.is_pregnant:
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="PREGNANCY",
                        severity="ABSOLUTE",
                        reason=(
                            "Contraindicado en el embarazo: riesgo de toxicidad fetal por absorción de "
                            "derivados salicilados (riesgo de cierre prematuro del conducto arterioso, "
                            "alteraciones de la coagulación y potencial teratogénico)."
                        ),
                    )
                )

            # D) Lactancia
            if profile.is_lactating:
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="LACTATION",
                        severity="RELATIVE",
                        reason=(
                            "Contraindicado durante la lactancia: los derivados salicilados se excretan "
                            "en la leche materna con potencial riesgo de síndrome de Reye o sangrado en el lactante."
                        ),
                    )
                )

        # ---------------------------------------------------------------------
        # 2. Arctostaphylos uva-ursi (Gayuba - Arbutina / Hidroquinona)
        # ---------------------------------------------------------------------
        elif name == "Arctostaphylos uva-ursi":
            # A) Embarazo
            if profile.is_pregnant:
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="PREGNANCY",
                        severity="ABSOLUTE",
                        reason=(
                            "Contraindicado en el embarazo: la arbutina experimenta hidrólisis metabólica "
                            "en hidroquinona libre, agente con potencial embriotóxico, mutagénico y citotóxico."
                        ),
                    )
                )

            # B) Lactancia
            if profile.is_lactating:
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="LACTATION",
                        severity="ABSOLUTE",
                        reason=(
                            "Contraindicado durante la lactancia: paso de hidroquinona libre y sus metabolitos "
                            "glucuronados al torrente mamario y leche materna."
                        ),
                    )
                )

            # C) Alergia a ericáceas o arbutina
            if any(term in a for a in allergies for term in ("arbutina", "gayuba", "uva-ursi", "ericace")):
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="ALLERGY",
                        severity="ABSOLUTE",
                        reason="Contraindicado por alergia conocida a Arctostaphylos uva-ursi o derivados de arbutina.",
                    )
                )

        # ---------------------------------------------------------------------
        # 3. Glycyrrhiza glabra (Regaliz - Glabridina / Ácido glicirrícico)
        # ---------------------------------------------------------------------
        elif name == "Glycyrrhiza glabra":
            # A) Embarazo
            if profile.is_pregnant:
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="PREGNANCY",
                        severity="ABSOLUTE",
                        reason=(
                            "Contraindicado en el embarazo: el ácido glicirrícico y las isoflavonas del regaliz "
                            "poseen actividad fitoestrogénica y alteran la barrera placentaria de 11β-HSD2, "
                            "incrementando el cortisol fetal y el riesgo de parto prematuro."
                        ),
                    )
                )

            # B) Alergia a Fabaceae o flavonoides
            if any(term in a for a in allergies for term in ("regaliz", "glycyrrhiza", "flavonoid", "fabace")):
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="ALLERGY",
                        severity="ABSOLUTE",
                        reason="Contraindicado por hipersensibilidad diagnosticada a Glycyrrhiza glabra o flavonoides.",
                    )
                )

        # ---------------------------------------------------------------------
        # 4. Melaleuca alternifolia (Árbol del té - Terpenos)
        # ---------------------------------------------------------------------
        elif name == "Melaleuca alternifolia":
            # A) Alergia a aceites esenciales o Melaleuca
            if any(term in a for a in allergies for term in ("melaleuca", "arbol del te", "tea tree", "terpenos")):
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="ALLERGY",
                        severity="ABSOLUTE",
                        reason=(
                            "Contraindicado por hipersensibilidad o dermatitis alérgica de contacto previa "
                            "al aceite esencial de Melaleuca alternifolia o terpenos."
                        ),
                    )
                )

        # ---------------------------------------------------------------------
        # 5. Centella asiatica (Gotu Kola - Triterpenos)
        # ---------------------------------------------------------------------
        elif name == "Centella asiatica":
            # A) Heridas abiertas o eccemas exudativos no epitelizados
            if profile.has_open_wounds:
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="CLINICAL_RESTRICTION",
                        severity="ABSOLUTE",
                        reason=(
                            "Contraindicado sobre heridas abiertas no epitelizadas o eccemas exudativos agudos: "
                            "riesgo de sobreestimulación granulomatosa e irritación profunda."
                        ),
                    )
                )

            # B) Alergia a Apiaceae (Umbelíferas)
            if any(term in a for a in allergies for term in ("centella", "gotu kola", "apiace", "umbelifer")):
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="ALLERGY",
                        severity="ABSOLUTE",
                        reason="Contraindicado por hipersensibilidad conocida a Centella asiatica o plantas Apiaceae.",
                    )
                )

        # ---------------------------------------------------------------------
        # 6. Camellia sinensis (Té verde - Polifenoles / EGCG)
        # ---------------------------------------------------------------------
        elif name == "Camellia sinensis":
            if any(term in a for a in allergies for term in ("camellia", "te verde", "té verde", "polifenoles")):
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="ALLERGY",
                        severity="ABSOLUTE",
                        reason="Contraindicado por hipersensibilidad o dermatitis alérgica a Camellia sinensis.",
                    )
                )

        # ---------------------------------------------------------------------
        # 7. Rosa canina (Rosa mosqueta - Ácidos grasos y retinol vegetal)
        # ---------------------------------------------------------------------
        elif name == "Rosa canina":
            if profile.has_cystic_acne:
                issues.append(
                    ContraindicationIssue(
                        species=name,
                        common_name=common,
                        category="CLINICAL_RESTRICTION",
                        severity="ABSOLUTE",
                        reason=(
                            "Contraindicado en acné quístico activo: la fracción lipídica rica en ácidos grasos "
                            "puede favorecer la formación de tapones comedogénicos en folículos inflamados."
                        ),
                    )
                )

        return issues

    def is_compound_safe(self, compound: BotanicalCompound, profile: PatientProfile) -> bool:
        """Determina si un compuesto carece de contraindicaciones absolutas para el paciente."""
        issues = self.check_contraindications(compound, profile)
        return not any(i.severity in ("ABSOLUTE", "RELATIVE") for i in issues)

    def get_therapeutic_substitute(
        self,
        compound: BotanicalCompound | str,
        profile: PatientProfile,
    ) -> Optional[BotanicalCompound]:
        """
        Encuentra el activo de reemplazo terapéutico seguro para un compuesto contraindicado,
        verificando rigurosamente que el sustituto no posea contraindicaciones clínicas
        frente al perfil particular del paciente.
        """
        name = compound if isinstance(compound, str) else compound.scientific_name
        candidates = THERAPEUTIC_SUBSTITUTIONS.get(name, ())
        for candidate in candidates:
            if self.is_compound_safe(candidate, profile):
                return candidate
        return None

    def get_substitutions_for_contraindications(
        self,
        contraindicated_species: List[str],
        profile: PatientProfile,
    ) -> Dict[str, BotanicalCompound]:
        """Calcula los sustitutos terapéuticos seguros para una lista de especies contraindicadas."""
        subs: Dict[str, BotanicalCompound] = {}
        for sp in contraindicated_species:
            safe_sub = self.get_therapeutic_substitute(sp, profile)
            if safe_sub is not None:
                subs[sp] = safe_sub
        return subs

    def evaluate(
        self,
        profile: PatientProfile,
        auto_substitute: bool = False,
    ) -> PrescriptionResult:
        """
        Evalúa integralmente el perfil del paciente:
        1. Clasifica el estrato de edad biológica.
        2. Determina la indicación fitoterapéutica primaria.
        3. Recupera los activos botánicos candidatos para el estrato.
        4. Aplica el filtro de contraindicaciones farmacológicas y clínicas.
        5. Determina sustituciones terapéuticas seguras para activos contraindicados
           (ej. evitar Salix alba en piel sensible y prescribir Melaleuca alternifolia).
        6. Genera advertencias clínicas pertinentes.

        Args:
            profile: Perfil clínico del paciente con banderas de seguridad.
            auto_substitute: Si es True, añade los sustitutos terapéuticos seguros
                             directamente a las prescripciones aprobadas si no estaban ya.
        """
        age_group = self.get_age_group(profile.age)
        indication = self.get_primary_indication(age_group)
        candidates = self.get_candidate_compounds(age_group)

        approved: List[BotanicalCompound] = []
        contraindicated: Dict[str, List[ContraindicationIssue]] = {}
        warnings: List[str] = []

        # Agregar advertencias clínicas generales si aplican
        if profile.is_pregnant:
            warnings.append(
                "Paciente en estado de gestación: prescripción estrictamente restringida a activos "
                "de probada inocuidad obstétrica. Monitoreo obstétrico recomendado."
            )
        if profile.sensitive_skin:
            warnings.append(
                "Piel sensible o reactiva detectada: evitar queratolíticos desestabilizadores; "
                "priorizar formulaciones con pH fisiológico (5.5) y excipientes calmantes."
            )

        for compound in candidates:
            issues = self.check_contraindications(compound, profile)
            if issues:
                contraindicated[compound.scientific_name] = issues
            else:
                approved.append(compound)

        # ---------------------------------------------------------------------
        # Resolución de Sustituciones Terapéuticas Seguras
        # ---------------------------------------------------------------------
        substitutions: Dict[str, BotanicalCompound] = {}
        for contra_name, issues in contraindicated.items():
            sub = self.get_therapeutic_substitute(contra_name, profile)
            if sub is not None:
                substitutions[contra_name] = sub
                # Notificar la sustitución en advertencias clínicas
                category_desc = issues[0].category if issues else "contraindicación"
                warnings.append(
                    f"Sustitución terapéutica: {contra_name} contraindicado ({category_desc}); "
                    f"se prescribe {sub.common_name} ({sub.scientific_name}) como alternativa segura."
                )
                if auto_substitute and sub not in approved:
                    approved.append(sub)

        return PrescriptionResult(
            profile=profile,
            age_group=age_group,
            primary_indication=indication,
            approved_prescriptions=approved,
            contraindicated_prescriptions=contraindicated,
            clinical_warnings=warnings,
            substitutions=substitutions,
        )


_DEFAULT_CLINICAL_ENGINE: Optional[AgeStratifiedRulesEngine] = None


def get_clinical_engine() -> AgeStratifiedRulesEngine:
    """Singleton getter para el motor clínico fitoterapéutico."""
    global _DEFAULT_CLINICAL_ENGINE
    if _DEFAULT_CLINICAL_ENGINE is None:
        _DEFAULT_CLINICAL_ENGINE = AgeStratifiedRulesEngine()
    return _DEFAULT_CLINICAL_ENGINE


# ============================================================================
# Helpers Clínicos Modulares para Perfiles de Paciente y Sustituciones
# ============================================================================

def modify_patient_profile(profile: PatientProfile, **flags) -> PatientProfile:
    """
    Modifica interactivamente banderas clínicas de un PatientProfile existente.
    Acepta parámetros tanto en inglés (sensitive_skin, is_pregnant) como en español
    (piel_sensible, embarazo, acne_quistico).

    Returns:
        PatientProfile: La misma instancia del perfil modificada para fluidez.
    """
    return profile.update_flags(**flags)


def toggle_patient_profile_flag(
    profile: PatientProfile,
    flag_name: str,
    state: Optional[bool] = None,
) -> bool:
    """
    Alterna o establece una bandera clínica específica en el perfil del paciente.

    Args:
        profile: Instancia del perfil del paciente.
        flag_name: Nombre de la bandera (ej. 'sensitive_skin', 'piel_sensible', 'is_pregnant').
        state: Valor explícito o None para alternar (inversión lógica).

    Returns:
        bool: Nuevo valor de la bandera clínica.
    """
    return profile.toggle_flag(flag_name, state=state)


def get_safe_substitution(
    compound: BotanicalCompound | str,
    profile: PatientProfile,
    engine: Optional[AgeStratifiedRulesEngine] = None,
) -> Optional[BotanicalCompound]:
    """
    Recupera el principio activo sustituto seguro para un compuesto contraindicado.
    """
    eng = engine or get_clinical_engine()
    return eng.get_therapeutic_substitute(compound, profile)


def evaluate_with_substitutions(
    profile: PatientProfile,
    engine: Optional[AgeStratifiedRulesEngine] = None,
) -> PrescriptionResult:
    """
    Evalúa el perfil de paciente incorporando automáticamente sustituciones terapéuticas
    activas en las prescripciones aprobadas cuando los activos primarios están contraindicados.
    """
    eng = engine or get_clinical_engine()
    return eng.evaluate(profile, auto_substitute=True)
