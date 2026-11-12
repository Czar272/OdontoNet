# Ficha del modelo — visibilidad de piezas dentales en fotografías intraorales (ODON-267)

> Borrador. Las secciones de resultados se completan con `research/summarize.py` (`results/resumen-odon267.md`) cuando terminen las corridas. Estructura basada en las «model cards» de Mitchell et al. (2019), cita pendiente de verificar (fila 93 de `CITAS-PENDIENTES.md`).

## 1. Detalles del modelo

| Campo | Valor |
| --- | --- |
| Modelo principal | YOLO11s-seg (Ultralytics 8.4.191), segmentación de instancias, 32 clases (piezas permanentes FDI 11–48) |
| Comparador | RF-DETR Seg Small (rfdetr 1.11.2), planificado con las mismas clases, datos y partición. **Pasó a trabajo futuro** el 2026-11-12 por cómputo; solo se midió su viabilidad (ODON-266) |
| Inicialización | Pesos generales COCO de cada proyecto (*transfer learning*); ningún peso dental previo |
| Entrenamiento | Un solo modelo para las 5 vistas; 640 px (YOLO) y 384 px (RF-DETR); precisión mixta; **sin volteo horizontal**, porque el espejo cambia el cuadrante FDI |
| Desarrollador | Proyecto de tesis OdontoNet (UVG), ODON-267 |
| Licencias | YOLO11: AGPL-3.0. RF-DETR: Apache-2.0. Datos de entrenamiento: CC BY-NC-SA 4.0. **Los pesos entrenados quedan en la línea de tesis y no se distribuyen a clínicas** (ODON-275). |
| Reproducibilidad | `research/train.py` registra la semilla, la fracción, el hash de la lista de pacientes, el hash de la partición y el SHA-256 de los pesos en `results/entrenamiento/*.json` |

## 2. Uso previsto

- **Para qué:** proponer, en un periodontograma en borrador, qué piezas **no son visibles** en las fotos del paciente, como sugerencia que un doctor acepta o rechaza una por una (`docs/AI_INTEGRATION.md`).
- **Usuarios:** odontólogos de la clínica, dentro de OdontoNet.
- **Fuera de alcance:**
  - Diagnosticar o clasificar enfermedad periodontal.
  - Medir sondaje, sangrado, recesión, movilidad o furcación.
  - Decidir por sí mismo que una pieza está **ausente**: «no visible» incluye piezas no erupcionadas, retenidas o fuera de cuadro, y la equivalencia con «ausente» la decide el profesional.
  - Usarse sin revisión profesional.
  - Usarse en dentición temporal: el modelo no tiene clases 51–85.

## 3. Factores

- **Vista:** frontal, laterales y oclusales. Los resultados se informan por vista.
- **Grupo de piezas:** los terceros molares (18, 28, 38, 48) tienen unas 10 veces menos ejemplos y se informan aparte.
- **Población y equipo:** un solo dataset público (IOP-Compass, Italia, fotografía clínica estandarizada). No se ha medido el desempeño con fotos de teléfono ni con la población de la clínica; eso corresponde a ODON-272.

## 4. Métricas

- **Criterio de aceptación** (fijado el 2026-11-12, antes de evaluar; `docs/AI_INTEGRATION.md` §7.3):
  - Medida: sensibilidad de «no visible» ≥ 0,80 y especificidad ≥ 0,95.
  - Alcance: presencia por pieza y paciente con las 5 vistas combinadas, piezas 11–47, conjunto de prueba.
  - Umbral: elegido solo en validación.
  - IC 95 % por bootstrap por paciente.
- **Descriptivas:** mAP de máscara (IoU 0,50 y 0,50:0,95) y exactitud de numeración por vista, calculadas con el mismo código para ambos modelos (`research/evaluate.py`).
- **Por qué pesa más la especificidad:** un «no visible» falso, si se acepta, vacía las mediciones de una pieza presente.

## 5. Datos de evaluación

- **Conjunto de prueba de IOP-Compass:** 100 pacientes × 5 vistas, partición por paciente con semilla 42 (`results/particion-iop.json`), sin pacientes en común con entrenamiento ni validación.
- **Posiciones no visibles:** 30 sin terceros molares, de 2800. El intervalo de la sensibilidad será amplio, de unos ±15 puntos.
- **Uso único:** el conjunto de prueba se evalúa **una vez** por modelo. Una segunda evaluación queda marcada como exploratoria y no cuenta.

## 6. Datos de entrenamiento

- **Partición:** IOP-Compass, 700 pacientes de entrenamiento y 200 de validación, fotos reducidas a 1280 px.
- **Etiquetas:** contornos por pieza con FDI. Coherencia geométrica comprobada: en el 100 % de 968 fotos frontales la 11 queda a la izquierda de la 21 y por encima de la 41 (`results/auditoria-iop.json`).
- **Curva de aprendizaje (solo YOLO):** subconjuntos anidados del 25, 50 y 100 % de los pacientes de entrenamiento. Se planeó con 5 semillas y luego con 2; se midió con 1 (ver §7.4).

## 7. Resultados

Modelo `yolo11s-seg-f100-s0`:
- **Entrenamiento:** 700 pacientes; parada temprana en la época 89, con la mejor en la 69.
- **Pesos:** SHA-256 `9e9abf1b22b7931373f8a788191af3bc6c666e2139f92a86bf1a699d19a35ec1`.
- **Umbral de operación:** 0,927, congelado en validación.
- **Conjunto de prueba:** 100 pacientes, **evaluado una sola vez**.
- **Fuentes:** `results/evaluacion/yolo11s-seg-f100-s0-{umbral,test}.json` y `results/resumen-odon267.md`.

### 7.1 Criterio de aceptación (presencia por pieza y paciente, piezas 11–47)

| Métrica | Valor | IC 95 % (bootstrap por paciente) | Exigido |
| --- | --- | --- | --- |
| Sensibilidad de «no visible» | 0,90 (27/30) | 0,80–1,00 | ≥ 0,80 |
| Especificidad | 0,963 (2668/2770) | 0,950–0,974 | ≥ 0,95 |

**Cumple.**
- **Precisión del resultado:** los dos IC tocan el mínimo exigido, porque solo hay 30 posiciones no visibles en prueba.
- **Falsos «no visible»:** hay 102 piezas visibles que el modelo no ve con el umbral elegido. Con la baja prevalencia de lo no visible, el valor predictivo positivo de una sugerencia «no visible» es de 27/129 ≈ 0,21: **la mayoría de las sugerencias «no visible» serían incorrectas** y el profesional debe rechazarlas. Esto refuerza que la sugerencia sea una propuesta para revisar y no un registro automático.

### 7.2 Por vista (conjunto de prueba, 100 fotos por vista)

| Vista | mAP50 de máscara | mAP50-95 de máscara | Numeración correcta* | Piezas detectadas con el umbral** |
| --- | --- | --- | --- | --- |
| Frontal | 0,92 | 0,78 | 0,99 | 0,64 |
| Lateral derecha | **0,70** | 0,60 | 0,97 | 0,71 |
| Lateral izquierda | 0,85 | 0,73 | 0,97 | 0,73 |
| Oclusal superior | 0,88 | 0,84 | 0,99 | 0,95 |
| Oclusal inferior | 0,90 | 0,86 | 0,99 | 0,92 |
| Todas | 0,92 | 0,82 | 0,98 | 0,76 |

\* De las piezas anotadas que el modelo encuentra (IoU ≥ 0,5, sin mirar la clase), proporción con el número FDI correcto.
\*\* Con el umbral de operación, que es alto (0,927). La decisión por paciente combina las 5 vistas.

La diferencia entre la lateral derecha (0,70) y la izquierda (0,85) no tiene una explicación comprobada. Queda como hallazgo por investigar: puede deberse a las fotos, a la anotación o al modelo.

### 7.3 Terceros molares (18, 28, 38, 48)

En prueba, 320 de 400 posiciones no son visibles:
- **Sensibilidad de «no visible»:** 0,997 (IC 0,99–1,00).
- **Especificidad:** **0,41** (IC 0,28–0,53). El modelo no ve muchos terceros molares que sí están.

Por eso el servicio **nunca** los sugiere como «no visible» (`never_absent` en los metadatos del modelo, ODON-269).

### 7.4 Curva de aprendizaje y comparación

**Curva (medida el 2026-11-12):** semilla 0, 30 épocas por corrida, cada punto con su propio umbral congelado en validación y evaluado una vez en prueba. Fuentes: `results/evaluacion/yolo11s-seg-f{25,50,100}-s0-e30-*.json` y `results/resumen-odon267.md`.

| % de pacientes | Umbral | mAP50 de máscara | Numeración | Sensibilidad «no visible» (IC 95 %) | Especificidad (IC 95 %) | Especificidad terceros molares (IC 95 %) |
| --- | --- | --- | --- | --- | --- | --- |
| 25 (175) | 0,920 | 0,89 | 0,98 | 0,80 (0,62–0,97) | 0,960 (0,948–0,970) | 0,28 (0,17–0,37) |
| 50 (350) | 0,927 | 0,91 | 0,98 | 0,90 (0,76–1,00) | 0,947 (0,931–0,961) | 0,41 (0,28–0,54) |
| 100 (700) | 0,926 | 0,92 | 0,99 | 0,87 (0,74–1,00) | 0,953 (0,938–0,967) | 0,50 (0,36–0,62) |

Nota de trazabilidad: la prueba del punto de 100 % pudo calcularse dos veces en paralelo (el script de la curva siguió activo tras su corte y coincidió con la evaluación manual), con los mismos pesos, el mismo umbral congelado, el bootstrap con semilla fija y sin decisiones intermedias. El JSON guardado es el de la última escritura; la inferencia en GPU puede variar mínimamente entre ejecuciones.

**Lectura:**
- La segmentación (mAP50) y la especificidad de los terceros molares mejoran con más pacientes en los tres puntos.
- Para el criterio de presencia (piezas 11–47) no se ve una tendencia: las diferencias entre puntos son de 1 a 3 falsos «no visible» y todos los IC se solapan.
- El modelo principal (100 %, 89 épocas, §7.1) supera al punto de 100 % a 30 épocas en especificidad (0,963 frente a 0,953), lo que sugiere que el número de épocas pesa tanto como el de pacientes. Es una observación, no una comparación pareada.

**Por qué se detuvo y qué falta:**
- **Medido:** 3 puntos con 1 semilla. Es una curva **exploratoria**: sin una segunda semilla no hay estimación de la variabilidad entre entrenamientos.
- **No medido:** la semilla 1 (unas 2,5 h en la RTX 4050 del portátil). La primera ejecución de la curva se detuvo por falta de memoria RAM del equipo durante la corrida de 100 %, y el cierre del proyecto se fijó para el 2026-11-12.
- **Proyectado, con su base:** no se afirma si más pacientes mejorarían el criterio de presencia. Con 30 posiciones no visibles en prueba, un falso «no visible» mueve la sensibilidad 0,033, así que para distinguir tendencias haría falta un conjunto de prueba con más piezas ausentes, no solo más semillas.

**Comparación con RF-DETR Seg Small:** trabajo futuro, por cómputo (unas 40 h de GPU). No se afirma cuál de los dos es mejor.

## 8. Consideraciones éticas

- **Datos:** solo datos públicos con licencia para investigación. No se usaron fotos de pacientes de la clínica; hacerlo requiere el dictamen de ética (ODON-220) y el consentimiento con `research_use`.
- **En el sistema:** el modelo no recibe identificadores, no guarda imágenes y no aplica nada sin revisión profesional (`docs/AI_INTEGRATION.md` §2 y §4.2).
- **Riesgo principal:** que se acepte como «ausente» una pieza presente pero no fotografiada. Lo mitigan:
  - el texto «no visible en las fotos»;
  - la confirmación para las sugerencias que vacían datos;
  - la exclusión de «aceptar todas» cuando hay conflicto con lo registrado.

## 9. Advertencias y limitaciones

- **Datos de un solo centro:** puede no generalizar a otras cámaras, iluminación o poblaciones.
- **Terceros molares:** su detección es débil.
- **Referencia:** es la anotación de visibilidad en fotos, no un examen clínico.
- **Confianza:** la puntuación del modelo no es una probabilidad calibrada.
- **Latencia en CPU:** medida en una laptop limitada a 2 y 4 núcleos (`docs/viabilidad.md`). Falta medirla en el equipo de la clínica.
