PRAGMA foreign_keys = ON;

-- Catálogo de Niveles de Severidad
INSERT OR IGNORE INTO severidad_niveles (severidad_id, codigo, umbral_min_pct, umbral_max_pct) VALUES
(1, 'NINGUNA', 0.0, 0.5),
(2, 'LEVE', 0.5, 2.0),
(3, 'MODERADA', 2.0, 4.0),
(4, 'ALTA', 4.0, 100.0);

-- Catálogo de Condiciones Objetivo
INSERT OR IGNORE INTO condiciones_objetivo (condicion_id, codigo, descripcion_clinica) VALUES
(1, 'HIPERPIGMENTACION', 'Presencia anómala de depósitos de melanina dérmica o epidérmica que generan manchas cutáneas (léntigos solares, melasma, PIH).'),
(2, 'ENVEJECIMIENTO_PREMATURO', 'Disminución prematura de elasticidad dérmica, degradación de colágeno y formación de líneas finas asociadas a fotoexposición solar.');

-- Catálogo Clínico de Especies Botánicas (Hermes Pharmacognosy Knowledge Base)
INSERT OR IGNORE INTO especies_botanicas (especie_id, nombre_cientifico, nombre_comun, precauciones) VALUES
(1, 'Arctostaphylos uva-ursi', 'Gayuba', 'No combinar simultáneamente con peróxido de benzoilo ni hidroquinona. Evitar exposición solar directa sin fotoprotección SPF 50+.'),
(2, 'Rosa canina', 'Rosa mosqueta', 'Fotosensibilidad en pieles reactivas; uso exclusivamente nocturno. No aplicar sobre lesiones activas de acné quístico.'),
(3, 'Glycyrrhiza glabra', 'Regaliz', 'Desaconsejado en pacientes con hipersensibilidad conocida a flavonoides o dermatitis perioral aguda.'),
(4, 'Camellia sinensis', 'Té verde', 'Puede provocar ligera sequedad en cutis alípicos si se usa en concentraciones superiores al 5%.'),
(5, 'Centella asiatica', 'Gotu Kola', 'Evitar en heridas abiertas no epitelizadas o eccemas exudativos. Posible sensibilización tópica rara.'),
(6, 'Salix alba', 'Sauce blanco', 'Contraindicado en pacientes con alergia demostrada a salicilatos o ácido acetilsalicílico.');

-- Motor de Reglas Botánicas Deterministas
-- Regla 1: Hiperpigmentación Preventiva en Edad Joven (18-35 años, NINGUNA -> Té Verde)
INSERT OR IGNORE INTO reglas_botanicas (regla_id, edad_min, edad_max, severidad_id, condicion_id, especie_id) VALUES
(101, 18, 35, 1, 1, 4),

-- Regla Canónica de Test: Edad 18-40, Severidad LEVE, HIPERPIGMENTACION -> Arctostaphylos uva-ursi
(1, 18, 40, 2, 1, 1),

-- Regla: Hiperpigmentación Leve en Adultos (41-60 años, LEVE -> Arctostaphylos uva-ursi)
(102, 41, 60, 2, 1, 1),

-- Regla: Hiperpigmentación Moderada Adulto Joven (25-45 años, MODERADA -> Gayuba + Té Verde)
(103, 25, 45, 3, 1, 1),
(104, 25, 45, 3, 1, 4),

-- Regla: Hiperpigmentación Moderada Maduro (46-70 años, MODERADA -> Regaliz + Té Verde)
(105, 46, 70, 3, 1, 3),
(106, 46, 70, 3, 1, 4),

-- Reglas Canónicas de Test: Edad 50-90, Severidad ALTA, HIPERPIGMENTACION -> Rosa canina + Glycyrrhiza glabra
(2, 50, 90, 4, 1, 2),
(3, 50, 90, 4, 1, 3),

-- Regla: Hiperpigmentación Alta y Queratosis en Adulto Joven (18-49 años, ALTA -> Sauce blanco)
(107, 18, 49, 4, 1, 6),

-- Reglas para Envejecimiento Prematuro (Anti-aging regenerativo)
(201, 30, 55, 2, 2, 5), -- 30-55 años, Leve -> Centella asiatica
(202, 40, 70, 3, 2, 2), -- 40-70 años, Moderada -> Rosa canina
(203, 40, 70, 3, 2, 5), -- 40-70 años, Moderada -> Centella asiatica
(204, 50, 90, 4, 2, 2), -- 50-90 años, Alta -> Rosa canina
(205, 50, 90, 4, 2, 5); -- 50-90 años, Alta -> Centella asiatica
