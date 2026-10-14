PRAGMA foreign_keys = ON;

-- Catálogos Atómicos
CREATE TABLE IF NOT EXISTS severidad_niveles (
    severidad_id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE, -- 'NINGUNA', 'LEVE', 'MODERADA', 'ALTA'
    umbral_min_pct REAL NOT NULL,
    umbral_max_pct REAL NOT NULL,
    CONSTRAINT chk_umbrales CHECK (umbral_min_pct < umbral_max_pct)
);

CREATE TABLE IF NOT EXISTS condiciones_objetivo (
    condicion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE, -- 'HIPERPIGMENTACION', 'ENVEJECIMIENTO_PREMATURO'
    descripcion_clinica TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS especies_botanicas (
    especie_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_cientifico TEXT NOT NULL UNIQUE,
    nombre_comun TEXT NOT NULL,
    precauciones TEXT NOT NULL
);

-- Motor de Reglas Determinista
CREATE TABLE IF NOT EXISTS reglas_botanicas (
    regla_id INTEGER PRIMARY KEY AUTOINCREMENT,
    edad_min INTEGER NOT NULL,
    edad_max INTEGER NOT NULL,
    severidad_id INTEGER NOT NULL,
    condicion_id INTEGER NOT NULL,
    especie_id INTEGER NOT NULL,
    CONSTRAINT fk_regla_severidad FOREIGN KEY (severidad_id) REFERENCES severidad_niveles(severidad_id) ON DELETE RESTRICT,
    CONSTRAINT fk_regla_condicion FOREIGN KEY (condicion_id) REFERENCES condiciones_objetivo(condicion_id) ON DELETE RESTRICT,
    CONSTRAINT fk_regla_especie FOREIGN KEY (especie_id) REFERENCES especies_botanicas(especie_id) ON DELETE RESTRICT,
    CONSTRAINT chk_rango_edad CHECK (edad_min <= edad_max),
    CONSTRAINT uq_regla_unica UNIQUE (edad_min, edad_max, severidad_id, condicion_id, especie_id)
);

-- Entidad Principal: Sesión de Diagnóstico (Anónima)
CREATE TABLE IF NOT EXISTS sesiones_diagnostico (
    sesion_id TEXT PRIMARY KEY, -- UUID v5 determinista (Namespace + Hash de inputs)
    severidad_id INTEGER NOT NULL,
    edad_estimada INTEGER NOT NULL,
    porcentaje_manchas REAL NOT NULL,
    tiempo_procesamiento_ms REAL NOT NULL,
    creado_en TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CONSTRAINT fk_sesion_severidad FOREIGN KEY (severidad_id) REFERENCES severidad_niveles(severidad_id) ON DELETE RESTRICT
);

-- Tabla de Detalle: Prescripciones Asignadas a la Sesión
CREATE TABLE IF NOT EXISTS sesion_prescripciones (
    sesion_id TEXT NOT NULL,
    regla_id INTEGER NOT NULL,
    PRIMARY KEY (sesion_id, regla_id),
    CONSTRAINT fk_sp_sesion FOREIGN KEY (sesion_id) REFERENCES sesiones_diagnostico(sesion_id) ON DELETE CASCADE,
    CONSTRAINT fk_sp_regla FOREIGN KEY (regla_id) REFERENCES reglas_botanicas(regla_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_sesiones_fecha ON sesiones_diagnostico(creado_en);
