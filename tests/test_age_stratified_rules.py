"""
Unit Tests para el Motor de Reglas Clínicas Estratificadas por Edad y Contraindicaciones Médicas.

Valida:
1. Estratificación etaria según criterios dermatoscópicos y fitoterapéuticos:
   - Piel Joven (<25 años): Seborregulación y queratolíticos suaves (Melaleuca alternifolia, Salix alba).
   - Piel Adulta (25 a 39 años): Inhibición de tirosinasa y tono (Arctostaphylos uva-ursi, Glycyrrhiza glabra).
   - Piel Madura (>=40 años): Síntesis de colágeno y antioxidantes celulares (Centella asiatica, Camellia sinensis).
2. Verificación y cumplimiento riguroso de contraindicaciones clínicas:
   - Salicilatos (Salix alba) en piel sensible o reactiva.
   - Salicilatos en alergia diagnosticada a salicilatos o ácido acetilsalicílico.
   - Restricciones en embarazo (Salix alba, Arctostaphylos uva-ursi, Glycyrrhiza glabra).
   - Restricciones en lactancia (Arctostaphylos uva-ursi, Salix alba).
   - Alergias botánicas específicas y lesiones activas (eccemas/heridas para Centella asiatica).
3. Integración con el motor de reglas general (RulesEngine) y base de datos SQLite 3NF.
"""

import pytest
import sqlite3
from src.domain.age_stratified_rules import (
    AgeGroup,
    classify_age_group,
    PatientProfile,
    BotanicalCompound,
    ContraindicationIssue,
    PrescriptionResult,
    AgeStratifiedRulesEngine,
    get_clinical_engine,
    BOTANICAL_CATALOG,
    MELALEUCA_ALTERNIFOLIA,
    SALIX_ALBA,
    ARCTOSTAPHYLOS_UVA_URSI,
    GLYCYRRHIZA_GLABRA,
    CENTELLA_ASIATICA,
    CAMELLIA_SINENSIS,
    ROSA_CANINA,
    THERAPEUTIC_SUBSTITUTIONS,
    modify_patient_profile,
    toggle_patient_profile_flag,
    get_safe_substitution,
    evaluate_with_substitutions,
)
from src.domain.rules_engine import RulesEngine, ClinicalRulesEngine
from src.db.database import get_db


# ============================================================================
# 1. Tests de Clasificación de Estratos Etarios (Boundary Value Analysis)
# ============================================================================

class TestAgeClassification:
    """Pruebas de límites para la clasificación en grupos etarios."""

    @pytest.mark.parametrize("age", [0, 14, 18, 20, 24])
    def test_edad_menor_25_clasifica_como_joven(self, age):
        assert classify_age_group(age) == AgeGroup.JOVEN

    @pytest.mark.parametrize("age", [25, 26, 30, 35, 39])
    def test_edad_25_a_39_clasifica_como_adulto(self, age):
        assert classify_age_group(age) == AgeGroup.ADULTO

    @pytest.mark.parametrize("age", [40, 41, 55, 65, 80, 100, 120])
    def test_edad_40_o_mas_clasifica_como_maduro(self, age):
        assert classify_age_group(age) == AgeGroup.MADURO

    def test_edad_negativa_lanza_value_error(self):
        with pytest.raises(ValueError, match="fuera del rango fisiológico"):
            classify_age_group(-1)

    def test_edad_excesiva_lanza_value_error(self):
        with pytest.raises(ValueError, match="fuera del rango fisiológico"):
            classify_age_group(121)


# ============================================================================
# 2. Tests de Prescripciones Botánicas para Piel Joven (<25 años)
# ============================================================================

class TestPielJovenRules:
    """
    Grupo Joven (edad < 25):
    Indicación primaria: Seborregulación y queratolíticos suaves
    Activos: Melaleuca alternifolia y Salix alba
    """

    @pytest.fixture
    def engine(self):
        return AgeStratifiedRulesEngine()

    def test_joven_sin_patologias_recibe_melaleuca_y_salix(self, engine):
        perfil = PatientProfile(edad=19)
        resultado = engine.evaluate(perfil)

        assert resultado.grupo_etario == AgeGroup.JOVEN
        assert "seborregulación" in resultado.indicacion_primaria.lower()
        assert len(resultado.prescripciones_aprobadas) == 2

        nombres_cientificos = resultado.approved_species
        assert "Melaleuca alternifolia" in nombres_cientificos
        assert "Salix alba" in nombres_cientificos

        # Validar principios activos esperados
        melaleuca = next(c for c in resultado.prescripciones_aprobadas if c.especie == "Melaleuca alternifolia")
        assert "Terpinen-4-ol" in melaleuca.principios_activos
        assert melaleuca.nombre_comun == "Árbol del té"

        salix = next(c for c in resultado.prescripciones_aprobadas if c.especie == "Salix alba")
        assert "Salicina" in salix.principios_activos
        assert salix.nombre_comun == "Sauce blanco"

    def test_joven_con_piel_sensible_contraindica_salix_alba(self, engine):
        """Salicilatos en piel sensible deben ser estrictamente contraindicados."""
        perfil = PatientProfile(edad=21, piel_sensible=True)
        resultado = engine.evaluate(perfil)

        assert "Salix alba" in resultado.contraindicated_species
        assert "Melaleuca alternifolia" in resultado.approved_species

        issues = resultado.prescripciones_contraindicadas["Salix alba"]
        assert any(i.category == "SENSITIVE_SKIN" for i in issues)
        assert any("disrupción de la barrera cutánea" in i.reason.lower() for i in issues)

    def test_joven_con_alergia_salicilatos_contraindica_salix_alba(self, engine):
        perfil = PatientProfile(edad=22, alergia_salicilatos=True)
        resultado = engine.evaluate(perfil)

        assert "Salix alba" in resultado.contraindicated_species
        issues = resultado.prescripciones_contraindicadas["Salix alba"]
        assert any(i.category == "SALICYLATE_ALLERGY" for i in issues)
        assert any("hipersensibilidad alérgica" in i.reason.lower() for i in issues)

    def test_joven_alergia_aspirina_en_lista_contraindica_salix(self, engine):
        perfil = PatientProfile(edad=20, known_allergies=["aspirina", "polen"])
        resultado = engine.evaluate(perfil)

        assert "Salix alba" in resultado.contraindicated_species
        issues = resultado.prescripciones_contraindicadas["Salix alba"]
        assert any(i.category == "SALICYLATE_ALLERGY" for i in issues)

    def test_joven_embarazada_contraindica_salix_alba(self, engine):
        perfil = PatientProfile(edad=23, embarazo=True)
        resultado = engine.evaluate(perfil)

        assert "Salix alba" in resultado.contraindicated_species
        issues = resultado.prescripciones_contraindicadas["Salix alba"]
        assert any(i.category == "PREGNANCY" for i in issues)
        assert any("conducto arterioso" in i.reason.lower() for i in issues)

    def test_joven_lactante_contraindica_salix_alba(self, engine):
        perfil = PatientProfile(edad=24, lactancia=True)
        resultado = engine.evaluate(perfil)

        assert "Salix alba" in resultado.contraindicated_species
        issues = resultado.prescripciones_contraindicadas["Salix alba"]
        assert any(i.category == "LACTATION" for i in issues)


# ============================================================================
# 3. Tests de Prescripciones Botánicas para Piel Adulta (25 <= edad < 40)
# ============================================================================

class TestPielAdultaRules:
    """
    Grupo Adulto (25 <= edad < 40):
    Indicación primaria: Inhibición de tirosinasa y tono
    Activos: Arctostaphylos uva-ursi (Gayuba) y Glycyrrhiza glabra (Regaliz)
    """

    @pytest.fixture
    def engine(self):
        return AgeStratifiedRulesEngine()

    def test_adulto_sin_patologias_recibe_gayuba_y_regaliz(self, engine):
        perfil = PatientProfile(edad=32)
        resultado = engine.evaluate(perfil)

        assert resultado.grupo_etario == AgeGroup.ADULTO
        assert "tirosinasa" in resultado.indicacion_primaria.lower()
        assert len(resultado.prescripciones_aprobadas) == 2

        especies = resultado.approved_species
        assert "Arctostaphylos uva-ursi" in especies
        assert "Glycyrrhiza glabra" in especies

        gayuba = next(c for c in resultado.prescripciones_aprobadas if c.especie == "Arctostaphylos uva-ursi")
        assert "Arbutina" in gayuba.principios_activos
        assert "peróxido de benzoilo" in gayuba.precauciones

        regaliz = next(c for c in resultado.prescripciones_aprobadas if c.especie == "Glycyrrhiza glabra")
        assert "Glabridina" in regaliz.principios_activos

    def test_adulto_embarazo_contraindica_gayuba_y_regaliz(self, engine):
        """En gestación, la arbutina y el regaliz deben ser estrictamente bloqueados."""
        perfil = PatientProfile(edad=29, embarazo=True)
        resultado = engine.evaluate(perfil)

        assert "Arctostaphylos uva-ursi" in resultado.contraindicated_species
        assert "Glycyrrhiza glabra" in resultado.contraindicated_species
        assert len(resultado.prescripciones_aprobadas) == 0

        uva_issues = resultado.prescripciones_contraindicadas["Arctostaphylos uva-ursi"]
        assert any("hidroquinona" in i.reason.lower() for i in uva_issues)

        regaliz_issues = resultado.prescripciones_contraindicadas["Glycyrrhiza glabra"]
        assert any("cortisol" in i.reason.lower() or "fitoestrogénica" in i.reason.lower() for i in regaliz_issues)

    def test_adulto_lactancia_contraindica_gayuba(self, engine):
        perfil = PatientProfile(edad=34, lactancia=True)
        resultado = engine.evaluate(perfil)

        assert "Arctostaphylos uva-ursi" in resultado.contraindicated_species
        issues = resultado.prescripciones_contraindicadas["Arctostaphylos uva-ursi"]
        assert any(i.category == "LACTATION" for i in issues)

        # Regaliz no está estrictamente contraindicado en lactancia aislada
        assert "Glycyrrhiza glabra" in resultado.approved_species

    def test_adulto_alergia_flavonoides_contraindica_regaliz(self, engine):
        perfil = PatientProfile(edad=30, known_allergies=["flavonoides"])
        resultado = engine.evaluate(perfil)

        assert "Glycyrrhiza glabra" in resultado.contraindicated_species
        assert "Arctostaphylos uva-ursi" in resultado.approved_species


# ============================================================================
# 4. Tests de Prescripciones Botánicas para Piel Madura (edad >= 40)
# ============================================================================

class TestPielMaduraRules:
    """
    Grupo Maduro (edad >= 40):
    Indicación primaria: Síntesis de colágeno y antioxidantes celulares
    Activos: Centella asiatica (Gotu Kola) y Camellia sinensis (Té verde)
    """

    @pytest.fixture
    def engine(self):
        return AgeStratifiedRulesEngine()

    def test_maduro_sin_patologias_recibe_centella_y_te_verde(self, engine):
        perfil = PatientProfile(edad=52)
        resultado = engine.evaluate(perfil)

        assert resultado.grupo_etario == AgeGroup.MADURO
        assert "colágeno" in resultado.indicacion_primaria.lower()
        assert len(resultado.prescripciones_aprobadas) == 2

        especies = resultado.approved_species
        assert "Centella asiatica" in especies
        assert "Camellia sinensis" in especies

        centella = next(c for c in resultado.prescripciones_aprobadas if c.especie == "Centella asiatica")
        assert "Madecasósido" in centella.principios_activos
        assert centella.nombre_comun == "Gotu Kola"

        te_verde = next(c for c in resultado.prescripciones_aprobadas if c.especie == "Camellia sinensis")
        assert any("EGCG" in c or "Epigalocatequina" in c for c in te_verde.principios_activos)

    def test_maduro_con_heridas_abiertas_contraindica_centella(self, engine):
        perfil = PatientProfile(edad=58, heridas_abiertas=True)
        resultado = engine.evaluate(perfil)

        assert "Centella asiatica" in resultado.contraindicated_species
        assert "Camellia sinensis" in resultado.approved_species

        issues = resultado.prescripciones_contraindicadas["Centella asiatica"]
        assert any(i.category == "CLINICAL_RESTRICTION" for i in issues)
        assert any("heridas abiertas" in i.reason.lower() for i in issues)

    def test_maduro_alergia_apiaceae_contraindica_centella(self, engine):
        perfil = PatientProfile(edad=45, known_allergies=["apiaceae"])
        resultado = engine.evaluate(perfil)

        assert "Centella asiatica" in resultado.contraindicated_species
        assert "Camellia sinensis" in resultado.approved_species


# ============================================================================
# 5. Tests de Modelos de Datos, Compatibilidad y Paridad Lingüística
# ============================================================================

class TestPatientProfileAndModels:
    """Verifica paridad de atributos en inglés/español y serialización de resultados."""

    def test_patient_profile_atributos_bilingues(self):
        p1 = PatientProfile(
            edad=28,
            piel_sensible=True,
            alergia_salicilatos=True,
            embarazo=True,
            lactancia=True,
            alergias_conocidas=["aspirina"],
            heridas_abiertas=False,
            acne_quistico=True,
        )

        assert p1.age == 28
        assert p1.edad == 28
        assert p1.sensitive_skin is True
        assert p1.piel_sensible is True
        assert p1.salicylate_allergy is True
        assert p1.alergia_salicilatos is True
        assert p1.is_pregnant is True
        assert p1.embarazo is True
        assert p1.is_lactating is True
        assert p1.lactancia is True
        assert "aspirina" in p1.known_allergies
        assert "aspirina" in p1.alergias
        assert p1.has_cystic_acne is True
        assert p1.acne_quistico is True

    def test_prescription_result_to_dict_estructura(self):
        engine = AgeStratifiedRulesEngine()
        perfil = PatientProfile(edad=20, piel_sensible=True)
        res = engine.evaluate(perfil)

        data = res.to_dict()
        assert "edad" in data
        assert data["edad"] == 20
        assert data["grupo_etario"] == "JOVEN"
        assert "prescripciones_aprobadas" in data
        assert len(data["prescripciones_aprobadas"]) == 1
        assert "prescripciones_contraindicadas" in data
        assert "Salix alba" in data["prescripciones_contraindicadas"]
        assert "advertencias_clinicas" in data


# ============================================================================
# 6. Tests del Motor de Reglas Integrado (RulesEngine)
# ============================================================================

class TestRulesEngineIntegration:
    """Pruebas de la fachada de RulesEngine y su integración con SQLite 3NF."""

    @pytest.fixture
    def rules_engine(self):
        return RulesEngine()

    def test_evaluate_clinical_case_shortcut(self, rules_engine):
        res = rules_engine.evaluate_clinical_case(
            age=22,
            sensitive_skin=True,
        )
        assert res.age_group == AgeGroup.JOVEN
        assert "Salix alba" in res.contraindicated_species
        assert "Melaleuca alternifolia" in res.approved_species

    def test_filter_db_prescriptions_by_safety(self, rules_engine):
        # Simular lista de prescripciones que vendrían de SQLite
        db_rows = [
            {
                "regla_id": 1,
                "condicion_objetivo": "HIPERPIGMENTACION",
                "especie": "Arctostaphylos uva-ursi",
                "nombre_comun": "Gayuba",
                "precauciones": "SPF 50+",
            },
            {
                "regla_id": 107,
                "condicion_objetivo": "HIPERPIGMENTACION",
                "especie": "Salix alba",
                "nombre_comun": "Sauce blanco",
                "precauciones": "No combinar con exfoliantes",
            },
        ]

        perfil_gestante = PatientProfile(edad=28, is_pregnant=True)
        seguros, bloqueados = rules_engine.filter_db_prescriptions_by_safety(db_rows, perfil_gestante)

        # En embarazo: tanto Arctostaphylos como Salix alba deben ser bloqueados
        assert len(seguros) == 0
        assert len(bloqueados) == 2
        especies_bloqueadas = [b["especie"] for b in bloqueados]
        assert "Arctostaphylos uva-ursi" in especies_bloqueadas
        assert "Salix alba" in especies_bloqueadas

    def test_evaluate_with_db_connection(self, rules_engine, setup_test_environment):
        """Verifica la orquestación completa con la base de datos de test SQLite."""
        db_path = setup_test_environment["db_path"]
        with get_db(db_path) as conn:
            # Paciente adulto sano con 1.5% manchas (LEVE)
            perfil = PatientProfile(
                edad=30,
                porcentaje_manchas=1.5,
                sensitive_skin=False,
                is_pregnant=False,
            )
            res = rules_engine.evaluate_with_db(conn, perfil)

            assert res["clinica"]["estrato_etario"] == "ADULTO"
            assert res["clinica"]["severidad"] == "LEVE"
            assert len(res["prescripciones_db_aprobadas"]) > 0
            especies_db = [p["especie"] for p in res["prescripciones_db_aprobadas"]]
            assert "Arctostaphylos uva-ursi" in especies_db
            assert len(res["prescripciones_db_contraindicadas"]) == 0

    def test_evaluate_with_db_embarazo_filtra_prescripciones(self, rules_engine, setup_test_environment):
        """Paciente embarazada con 1.5% manchas: la consulta a DB recupera Gayuba pero el motor de seguridad la filtra."""
        db_path = setup_test_environment["db_path"]
        with get_db(db_path) as conn:
            perfil = PatientProfile(
                edad=30,
                porcentaje_manchas=1.5,
                is_pregnant=True,
            )
            res = rules_engine.evaluate_with_db(conn, perfil)

            assert len(res["prescripciones_db_aprobadas"]) == 0
            assert len(res["prescripciones_db_contraindicadas"]) == 1
            assert res["prescripciones_db_contraindicadas"][0]["especie"] == "Arctostaphylos uva-ursi"


# ============================================================================
# 7. Tests de Modificadores Interactivos de Perfil Clínico (PatientProfile)
# ============================================================================

class TestPatientProfileInteractiveModifiers:
    """Verifica alternancia y modificación dinámica de banderas clínicas del paciente."""

    def test_toggle_sensitive_skin(self):
        profile = PatientProfile(edad=20)
        assert profile.sensitive_skin is False

        # Alternancia automática (inversión lógica)
        new_val = profile.toggle_sensitive_skin()
        assert new_val is True
        assert profile.sensitive_skin is True

        new_val = profile.toggle_sensitive_skin()
        assert new_val is False
        assert profile.sensitive_skin is False

        # Asignación explícita
        profile.toggle_sensitive_skin(state=True)
        assert profile.sensitive_skin is True

    def test_toggle_pregnancy(self):
        profile = PatientProfile(edad=28)
        assert profile.is_pregnant is False

        assert profile.toggle_pregnancy() is True
        assert profile.is_pregnant is True
        assert profile.embarazo is True

        assert profile.toggle_pregnancy() is False
        assert profile.is_pregnant is False

        profile.toggle_pregnancy(state=True)
        assert profile.is_pregnant is True

    def test_toggle_cystic_acne(self):
        profile = PatientProfile(edad=45)
        assert profile.has_cystic_acne is False

        assert profile.toggle_cystic_acne() is True
        assert profile.has_cystic_acne is True
        assert profile.acne_quistico is True

        assert profile.toggle_cystic_acne(False) is False
        assert profile.has_cystic_acne is False

    def test_toggle_lactation(self):
        profile = PatientProfile(edad=30)
        assert profile.toggle_lactation() is True
        assert profile.is_lactating is True
        assert profile.lactancia is True
        assert profile.toggle_lactation() is False

    def test_toggle_salicylate_allergy(self):
        profile = PatientProfile(edad=22)
        assert profile.toggle_salicylate_allergy() is True
        assert profile.salicylate_allergy is True
        assert profile.alergia_salicilatos is True

    def test_toggle_open_wounds(self):
        profile = PatientProfile(edad=55)
        assert profile.toggle_open_wounds() is True
        assert profile.has_open_wounds is True
        assert profile.heridas_abiertas is True

    def test_toggle_flag_by_string_bilingual(self):
        profile = PatientProfile(edad=25)

        # Inglés
        assert profile.toggle_flag("sensitive_skin") is True
        assert profile.sensitive_skin is True
        assert profile.toggle_flag("is_pregnant") is True
        assert profile.is_pregnant is True
        assert profile.toggle_flag("has_cystic_acne") is True
        assert profile.has_cystic_acne is True

        # Español
        assert profile.toggle_flag("piel_sensible") is False
        assert profile.sensitive_skin is False
        assert profile.toggle_flag("embarazo") is False
        assert profile.is_pregnant is False
        assert profile.toggle_flag("acne_quistico") is False
        assert profile.has_cystic_acne is False
        assert profile.toggle_flag("heridas_abiertas") is True
        assert profile.has_open_wounds is True
        assert profile.toggle_flag("alergia_salicilatos") is True
        assert profile.salicylate_allergy is True
        assert profile.toggle_flag("lactancia") is True
        assert profile.is_lactating is True

    def test_toggle_flag_unknown_raises_key_error(self):
        profile = PatientProfile(edad=20)
        with pytest.raises(KeyError, match="Bandera clínica no reconocida"):
            profile.toggle_flag("bandera_inexistente")

    def test_fluent_setters_and_chaining(self):
        profile = PatientProfile(edad=24)
        result = (
            profile
            .set_sensitive_skin(True)
            .set_pregnant(True)
            .set_salicylate_allergy(True)
            .set_cystic_acne(True)
            .set_open_wounds(True)
            .set_lactating(True)
            .add_allergy("propoleo")
        )
        assert result is profile
        assert profile.sensitive_skin is True
        assert profile.is_pregnant is True
        assert profile.salicylate_allergy is True
        assert profile.has_cystic_acne is True
        assert profile.has_open_wounds is True
        assert profile.is_lactating is True
        assert "propoleo" in profile.known_allergies

    def test_update_flags_batch(self):
        profile = PatientProfile(edad=33)
        profile.update_flags(
            piel_sensible=True,
            embarazo=True,
            acne_quistico=True,
        )
        assert profile.sensitive_skin is True
        assert profile.is_pregnant is True
        assert profile.has_cystic_acne is True

    def test_allergy_addition_and_removal(self):
        profile = PatientProfile(edad=21, known_allergies=["polen"])
        profile.add_allergy("aspirina")
        assert "aspirina" in profile.known_allergies
        # No duplicados
        profile.add_allergy("aspirina")
        assert profile.known_allergies.count("aspirina") == 1

        profile.remove_allergy("polen")
        assert "polen" not in profile.known_allergies
        assert "aspirina" in profile.known_allergies

    def test_spanish_method_aliases(self):
        profile = PatientProfile(edad=27)
        assert profile.alternar_piel_sensible() is True
        assert profile.alternar_embarazo() is True
        assert profile.alternar_acne_quistico() is True
        assert profile.alternar_lactancia() is True
        assert profile.alternar_alergia_salicilatos() is True
        assert profile.alternar_heridas_abiertas() is True
        assert profile.alternar_bandera("piel_sensible") is False


# ============================================================================
# 8. Tests de Sustituciones Terapéuticas Seguras (Therapeutic Substitutions)
# ============================================================================

class TestTherapeuticSubstitutions:
    """
    Verifica que el motor sustituya adecuadamente los activos contraindicados:
    - Evitar Salix alba en piel sensible y prescribir Melaleuca alternifolia.
    - Sustituir activos en embarazo y lactancia.
    - Sustituir Rosa canina en acné quístico activo.
    """

    @pytest.fixture
    def engine(self):
        return AgeStratifiedRulesEngine()

    def test_sensitive_skin_substitutes_salix_alba_with_melaleuca(self, engine):
        """
        Requerimiento nuclear:
        En piel sensible, se evita Salix alba (salicilatos irritantes)
        y se prescribe Melaleuca alternifolia como sustitución segura.
        """
        perfil = PatientProfile(edad=20, sensitive_skin=True)
        resultado = engine.evaluate(perfil)

        # Salix alba debe estar contraindicado
        assert "Salix alba" in resultado.contraindicated_species

        # Melaleuca alternifolia debe estar aprobado y prescrito
        assert "Melaleuca alternifolia" in resultado.approved_species
        assert len(resultado.approved_prescriptions) == 1

        # Verificar registro explícito de sustitución terapéutica
        assert resultado.has_substitutions is True
        assert "Salix alba" in resultado.substitutions
        assert resultado.substitutions["Salix alba"].scientific_name == "Melaleuca alternifolia"
        assert resultado.substituted_species["Salix alba"] == "Melaleuca alternifolia"

        # Validar advertencia clínica detallada
        assert any("Melaleuca alternifolia" in w for w in resultado.clinical_warnings)

    def test_interactive_toggling_switches_prescriptions_safely(self, engine):
        """
        Demuestra la alternancia interactiva del perfil de paciente:
        1. Joven sano -> Recibe Salix alba y Melaleuca.
        2. Activa piel sensible interactiva -> Salix se bloquea, Melaleuca sustituye.
        3. Desactiva piel sensible interactiva -> Salix se restablece.
        """
        perfil = PatientProfile(edad=22)

        # Estado 1: Sin sensibilidad cutánea
        res1 = engine.evaluate(perfil)
        assert "Salix alba" in res1.approved_species
        assert "Melaleuca alternifolia" in res1.approved_species
        assert not res1.has_substitutions

        # Estado 2: Alternar interactivamente a piel sensible
        perfil.toggle_sensitive_skin()
        res2 = engine.evaluate(perfil)
        assert "Salix alba" in res2.contraindicated_species
        assert "Melaleuca alternifolia" in res2.approved_species
        assert res2.substituted_species["Salix alba"] == "Melaleuca alternifolia"

        # Estado 3: Restaurar piel sana interactiva
        perfil.toggle_sensitive_skin()
        res3 = engine.evaluate(perfil)
        assert "Salix alba" in res3.approved_species
        assert "Melaleuca alternifolia" in res3.approved_species

    def test_young_salicylate_allergy_substitutes_salix_with_melaleuca(self, engine):
        """Alergia a salicilatos bloquea Salix alba y prescribe Melaleuca."""
        perfil = PatientProfile(edad=19)
        perfil.toggle_salicylate_allergy()

        resultado = engine.evaluate(perfil)
        assert "Salix alba" in resultado.contraindicated_species
        assert "Melaleuca alternifolia" in resultado.approved_species
        assert resultado.substitutions["Salix alba"].scientific_name == "Melaleuca alternifolia"

    def test_young_sensitive_skin_and_melaleuca_allergy_fallback_camellia(self, engine):
        """
        Caso extremo clínico: paciente joven con piel sensible Y alergia a Melaleuca.
        Salix alba está contraindicado por piel sensible.
        Melaleuca alternifolia está contraindicada por alergia.
        El motor debe encontrar como sustituto seguro de segunda línea Camellia sinensis.
        """
        perfil = PatientProfile(edad=21, sensitive_skin=True, known_allergies=["melaleuca"])
        sub = engine.get_therapeutic_substitute("Salix alba", perfil)

        assert sub is not None
        assert sub.scientific_name == "Camellia sinensis"

        # Con evaluación con sustitución activa incorporada
        res = engine.evaluate(perfil, auto_substitute=True)
        assert "Salix alba" in res.contraindicated_species
        assert "Melaleuca alternifolia" in res.contraindicated_species
        assert "Camellia sinensis" in res.approved_species

    def test_adult_pregnancy_substitutions_camellia(self, engine):
        """
        En mujer adulta embarazada (30 años):
        Arctostaphylos uva-ursi (hidroquinona) y Glycyrrhiza glabra (cortisol/fitoestrógenos)
        están contraindicadas.
        El sistema propone como sustituto seguro de tono y antioxidación Camellia sinensis.
        """
        perfil = PatientProfile(edad=30, is_pregnant=True)
        res = engine.evaluate(perfil)

        assert "Arctostaphylos uva-ursi" in res.contraindicated_species
        assert "Glycyrrhiza glabra" in res.contraindicated_species
        assert res.has_substitutions is True

        sub_uva = res.substitutions.get("Arctostaphylos uva-ursi")
        assert sub_uva is not None
        assert sub_uva.scientific_name in ("Camellia sinensis", "Centella asiatica")

        # Con evaluate_with_substitutions helper
        res_sub = evaluate_with_substitutions(perfil, engine)
        assert len(res_sub.approved_prescriptions) > 0
        assert "Camellia sinensis" in res_sub.approved_species

    def test_mature_cystic_acne_substitutes_rosa_canina(self, engine):
        """
        En paciente maduro con acné quístico activo:
        Rosa canina está contraindicada por su fracción lipídica comedogénica.
        Sustituto seguro: Centella asiatica o Camellia sinensis.
        """
        perfil = PatientProfile(edad=52, has_cystic_acne=True)
        sub = engine.get_therapeutic_substitute("Rosa canina", perfil)

        assert sub is not None
        assert sub.scientific_name in ("Centella asiatica", "Camellia sinensis")

    def test_module_level_interactive_helpers(self):
        """Verifica las funciones helper a nivel de módulo."""
        perfil = PatientProfile(edad=23)

        # modify_patient_profile
        modificado = modify_patient_profile(perfil, piel_sensible=True)
        assert modificado.sensitive_skin is True

        # toggle_patient_profile_flag
        nuevo_estado = toggle_patient_profile_flag(perfil, "embarazo")
        assert nuevo_estado is True
        assert perfil.is_pregnant is True

        # get_safe_substitution
        sub = get_safe_substitution("Salix alba", perfil)
        assert sub is not None
        assert sub.scientific_name == "Melaleuca alternifolia"

