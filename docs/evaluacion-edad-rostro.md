# Evaluación de edad estimada por rostro

## Objetivo

Medir si la salida del modelo coincide mejor con la edad cronológica en la
cámara, iluminación y distancia reales del espejo. La imagen facial no aporta
una referencia objetiva de «edad biológica»; el ensayo valida concordancia con
la edad declarada, no un biomarcador clínico.

## Captura

- Participación voluntaria y edad declarada por la propia persona.
- Mantener la posición, luz difusa, exposición y distancia de la Raspberry.
- Esperar que el espejo termine el análisis y copiar la cifra mostrada.
- Tomar tres lecturas con pequeñas pausas; anotar únicamente el código anónimo,
  edad declarada, edad predicha y fototipo si la persona desea declararlo.
- No guardar fotografías, recortes faciales, nombres ni fechas de nacimiento.
- Usar un código aleatorio por persona y guardar el CSV fuera del repositorio.

CSV requerido: `participant_id,age_real,age_model`; `phototype` es opcional.
Cada participante debe conservar el mismo código durante sus lecturas. Reunir
al menos 20 personas distintas para que la herramienta pueda hacer una primera
separación por participantes; una evaluación más amplia dará resultados más
estables. Los datos pequeños son exploratorios, no validación clínica.

## Evaluación

`python scripts/evaluate_age_calibration.py /ruta/local/lecturas.csv`

La herramienta resume lecturas repetidas con mediana por persona, separa códigos
anónimos en calibración y prueba, aprende el offset en calibración y calcula el
MAE antes/después solo en personas reservadas. Muestra subgrupos de edad/fototipo
cuando hay al menos cinco personas en cada grupo. No aplica ni guarda offsets.

Si la prueba independiente mejora, repetir una segunda cohorte antes de cambiar
la calibración persistente (`data/config/calibracion_camara.json`). No escoger
offsets mirando el conjunto de prueba. Después, evaluar por separado la versión
INT8 y FP32: cuantizar un modelo puede introducir diferencias de predicción.
