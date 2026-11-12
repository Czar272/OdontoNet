# Ficha del modelo — visibilidad de piezas dentales en fotografías intraorales (ODON-267)

> Borrador. Las secciones de resultados se completan con `research/summarize.py` (`results/resumen-odon267.md`) cuando terminen las corridas. Estructura basada en las «model cards» de Mitchell et al. (2019), cita pendiente de verificar (fila 93 de `CITAS-PENDIENTES.md`).

## 1. Detalles del modelo

| Campo | Valor |
| --- | --- |
| Modelo principal | YOLO11s-seg (Ultralytics 8.4.191), segmentación de instancias, 32 clases (piezas permanentes FDI 11–48) |
| Comparador | RF-DETR Seg Small (rfdetr 1.11.2), mismas clases, mismos datos y misma partición |
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
- **Curva de aprendizaje (solo YOLO):** subconjuntos anidados del 25, 50, 75 y 100 % de los pacientes de entrenamiento, con 5 semillas.

## 7. Resultados

**Pendiente.** Se pegarán aquí las tablas de `results/resumen-odon267.md`:
- criterio de aceptación;
- resultados por vista;
- terceros molares;
- curva de aprendizaje;
- comparación con RF-DETR.

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
