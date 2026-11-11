# Integración del servicio de IA — contrato v1

> Estado: **contrato definido, sin implementar** (ODON-250, épica ODON-13). Lo implementan ODON-269 (microservicio), ODON-270 (backend) y ODON-271 (interfaz). Cualquier cambio a este documento que rompa compatibilidad sube la versión del contrato.

## 1. Alcance y límites

- La IA es **asistencia**: propone valores y un profesional decide. Ninguna sugerencia entra al periodontograma sin que un doctor la acepte; no hay aceptación automática. El sistema no emite diagnósticos ni clasifica la enfermedad.
- **Versión 1:** a partir de fotografías intraorales ya guardadas en el expediente, sugiere por pieza permanente FDI (11–48) si está **presente o ausente**. La numeración FDI la produce el modelo de segmentación de dientes (ODON-267).
- **Fuera de la versión 1:** sondaje, sangrado, supuración, nivel de inserción, movilidad y furcación no son observables en una fotografía y siguen siendo manuales. Recesión y placa son experimentos de tesis (ODON-274): se miden fuera de la interfaz y no se muestran como valores sugeridos.
- El periodontograma manual funciona igual sin el servicio. Si `AI_SERVICE_URL` está vacío, la función no aparece y el backend responde `503` a las rutas de análisis.

## 2. Componentes y flujo

```text
Navegador ──► API clínica (FastAPI) ──HTTP interno──► ai-service (CPU, sin internet)
                 │  lee las fotos de ImageStorage           │ no guarda nada
                 ▼                                           ▼
             PostgreSQL ◄── resultados y decisiones ──── respuesta JSON
```

1. Un doctor o administración elige de 1 a 5 fotos del paciente desde un examen en **borrador** y pide el análisis.
2. La API crea el análisis en estado `queued`, responde `202` y lo procesa en segundo plano: lee los archivos del almacenamiento privado y los envía al servicio.
3. El servicio responde con detecciones por foto y un resultado por pieza. La API guarda las sugerencias y deja el análisis en `completed` (o en `failed` con un código).
4. La interfaz consulta el estado y muestra las sugerencias junto a las fotos. Un doctor acepta o rechaza cada sugerencia, y lo aceptado se aplica al borrador como una revisión más.

**Privacidad:**
- El servicio no recibe nombre, identificadores de paciente ni de clínica. Recibe los bytes de cada foto, su vista y un identificador opaco (UUID aleatorio por análisis) para correlacionar registros.
- No escribe imágenes a disco ni registra su contenido, y sus registros solo contienen el UUID, los tiempos y los códigos de error.
- Escucha solo en la red interna de Docker: Caddy no lo publica y no tiene salida a internet.

## 3. API del servicio (`ai-service`)

Prefijo versionado `/v1`, JSON en UTF-8 y errores con el mismo formato que la API clínica: `{"detail": "<mensaje en español>", "code": "<código>"}`. Cada petición, salvo `/health`, lleva la cabecera `X-Service-Token` con el secreto compartido `AI_SERVICE_TOKEN`; si falta o no coincide, el servicio responde `401`.

### `GET /health`

`200 {"status": "ok"}` cuando el modelo está cargado; `503 {"status": "loading"}` mientras carga.

### `GET /v1/model`

```json
{
  "contract_version": "1",
  "model_name": "yolo11s-seg-teeth",
  "model_version": "2027.01.0",
  "weights_sha256": "<hash del archivo de pesos>",
  "task": "tooth_status",
  "labels": [11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25, 26, 27, 28,
             31, 32, 33, 34, 35, 36, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48],
  "limits": {"max_images": 5, "max_bytes_per_image": 15728640, "max_pixels": 50000000},
  "device": "cpu"
}
```

El nombre y la versión del modelo del ejemplo son ilustrativos. El backend guarda `model_name`, `model_version` y `weights_sha256` en cada análisis para que un resultado se pueda atribuir a un modelo exacto.

### `POST /v1/analyses/tooth-status`

`multipart/form-data`:

| Campo | Tipo | Regla |
| --- | --- | --- |
| `request_id` | UUID | Obligatorio; aleatorio, sin relación con ids de la base. |
| `images` | archivo, 1–5 | JPEG, PNG o WebP, como los guarda OdontoNet (ya re-codificados sin metadatos). |
| `views` | texto, uno por imagen y en el mismo orden | `frontal`, `right_lateral`, `left_lateral`, `upper_occlusal`, `lower_occlusal`, `detail`, `other` (los valores de `IMAGE_VIEWS`); una foto sin vista se envía como `other`. |

Respuesta `200`:

```json
{
  "contract_version": "1",
  "request_id": "6f1c…",
  "model": {"name": "yolo11s-seg-teeth", "version": "2027.01.0", "weights_sha256": "…"},
  "elapsed_ms": 4120,
  "images": [
    {
      "index": 0,
      "width": 4032, "height": 3024,
      "quality": {"usable": true, "reasons": []},
      "detections": [
        {"fdi": 11, "confidence": 0.94,
         "bbox": [0.41, 0.38, 0.49, 0.61],
         "polygon": [[0.42, 0.39], [0.48, 0.39], [0.48, 0.60], [0.42, 0.60]]}
      ]
    }
  ],
  "teeth": [
    {"fdi": 11, "status": "present", "confidence": 0.94, "evidence": [0]},
    {"fdi": 18, "status": "uncertain", "confidence": 0.31, "evidence": []},
    {"fdi": 36, "status": "absent", "confidence": 0.82, "evidence": [3, 4]}
  ]
}
```

- Las coordenadas están normalizadas a 0–1 respecto a la imagen: `bbox` es `[x1, y1, x2, y2]` y `polygon` es el contorno simplificado de la máscara, con 64 puntos como máximo.
- `teeth` trae siempre las 32 piezas. `status` puede ser `present`, `absent` o `uncertain`. `uncertain` aparece cuando ninguna vista muestra la zona con calidad suficiente o la confianza queda bajo el umbral de operación; nunca se convierte en sugerencia.
- `evidence` son los índices de las fotos que sustentan el resultado. Para `absent`, son las fotos donde la zona era visible y no se detectó la pieza.
- `confidence` es la puntuación del modelo, no una probabilidad calibrada. La interfaz no la presenta como porcentaje de acierto.
- `quality.usable = false` (con motivos como `blurred`, `too_dark` o `no_teeth_detected`) excluye esa foto del resultado por pieza, sin hacer fallar el análisis.

Errores del servicio:

| HTTP | `code` | Cuándo |
| --- | --- | --- |
| 400 | `invalid_request` | Faltan campos, `views` no coincide con `images` o una vista es desconocida. |
| 401 | `unauthorized` | Falta `X-Service-Token` o no coincide. |
| 413 | `image_too_large` | Una foto supera los límites de `/v1/model`. |
| 415 | `unsupported_image` | El contenido no es una imagen admitida. |
| 503 | `model_not_ready` | El modelo aún no está cargado. |
| 500 | `inference_error` | Fallo interno, sin trazas en la respuesta. |

## 4. API clínica (backend)

Rutas bajo `/patients/{patient_id}/periodontal-exams/{exam_id}/ai-analyses`, con la clínica del token como en todo el sistema.

| Ruta | Admin | Doctor | Recepción | Descripción |
| --- | --- | --- | --- | --- |
| `POST .../ai-analyses` | ✅ | ✅ | ⛔ 403 | Pide un análisis. Cuerpo `{"image_ids": [1–5 ids]}`. Responde `202` con el análisis en `queued`. |
| `GET .../ai-analyses` | ✅ | ✅ | ⛔ 403 | Análisis del examen, el más reciente primero. |
| `GET .../ai-analyses/{analysis_id}` | ✅ | ✅ | ⛔ 403 | Estado, fotos, modelo y sugerencias. |
| `POST .../ai-analyses/{analysis_id}/review` | ⛔ 403 | ✅ | ⛔ 403 | Acepta o rechaza sugerencias (ver 4.2). |

Un administrador que además tiene perfil de doctor revisa como doctor. La regla exacta de cómo un usuario `admin` con perfil de doctor obtiene ese permiso se fija al implementar ODON-270, junto con `PERMISSIONS.md` y la matriz del frontend.

### 4.1 Reglas al pedir un análisis

- **`404`** si el paciente, el examen o alguna foto no existen o son de otra clínica.
- **`422`** si `image_ids` está vacío, tiene más de 5 elementos o repetidos, o si alguna foto es de otro paciente o está anulada.
- **`409`** si el examen no es un borrador, o si ya hay un análisis `queued` o `running` para ese examen; la respuesta incluye `current_analysis_id`.
- **`503`** si `AI_SERVICE_URL` está vacío. El mensaje dice que el análisis automático no está disponible y que el periodontograma se puede llenar a mano.
- El pedido queda en la auditoría (`ai_analysis.requested`, solo ids).

### 4.2 Revisión

Cuerpo:

```json
{
  "base_revision": 7,
  "decisions": [
    {"suggestion_id": 101, "decision": "accepted"},
    {"suggestion_id": 102, "decision": "rejected"}
  ]
}
```

- `base_revision` es la revisión del examen sobre la que decidió el doctor. Si no coincide, la API responde `409` con `current_revision`, como en el guardado del borrador.
- Cada sugerencia se decide **una sola vez**: pasa de `pending` a `accepted` o a `rejected`. Si ya estaba decidida, la API responde `409`.
- Lo aceptado se aplica al borrador en la misma transacción y crea **una** revisión nueva. Aceptar `absent` marca la pieza como ausente y vacía sus mediciones, igual que hacerlo a mano. Aceptar `present` en una pieza marcada ausente la desmarca.
- La pieza aceptada queda con `source = 'ai'`, que significa «propuesto por la IA y aceptado por un doctor». Si después el profesional edita esa pieza, pasa a `manual`. El CHECK de `source` se amplía en la migración de ODON-270.
- **Conflicto con lo registrado:** una sugerencia que contradice una pieza con `source = 'manual'` y datos ya escritos llega con `conflicts_with_record = true`. «Aceptar todas» la excluye; se puede aceptar de forma individual, después de que la interfaz pida confirmación.
- «Aceptar todas» envía todas las sugerencias pendientes sin conflicto. Existe solo para presente/ausente: los tipos que se agreguen después se revisan uno por uno.
- Si el examen dejó de ser borrador (finalizado o anulado), la revisión responde `409` y las sugerencias quedan `pending` para siempre, como registro.
- La revisión queda en la auditoría (`ai_suggestions.reviewed`, ids y número de aceptadas y rechazadas).

## 5. Modelo de datos (migración de ODON-270)

Las tablas siguen los patrones existentes: FKs compuestas con `clinic_id` (decisión 1), nada se borra y las decisiones solo avanzan.

**`ai_analyses`**

- **Identificación y vínculos:**
  - `id`
  - `clinic_id`
  - `patient_id`: FK compuesta a `patients(id, clinic_id)`.
  - `exam_id`: FK compuesta a `periodontal_exams(id, clinic_id)`.
  - `request_uuid`: único.
- **Estado y autor:**
  - `status`: CHECK contra la lista de estados de §6.
  - `requested_by_user_id`
- **Modelo y contrato:** `contract_version`, `model_name`, `model_version` y `weights_sha256`, todos nulos hasta que el servicio responde.
- **Resultado:** `elapsed_ms` y `error_code`. `error_code` es obligatorio si `status = 'failed'` y nulo en cualquier otro estado.
- **Tiempos:** `created_at`, `started_at` y `finished_at`.
- **Índices:**
  - Índice único parcial sobre `exam_id` con la condición `WHERE status IN ('queued','running')`, que garantiza en la base un solo análisis activo por examen.
  - Índice sobre `(clinic_id, exam_id)`.

**`ai_analysis_images`**

- `analysis_id` e `image_id`, con FK compuesta a `patient_images(id, clinic_id)`.
- `position` (0–4) y la `view` usada en ese momento: las fotos pueden corregir su vista después.
- `usable` y `quality_reasons` (texto[]).
- `detections` (JSONB): la lista tal como la devolvió el servicio, con coordenadas normalizadas y sin píxeles.

**`ai_suggestions`**

- `analysis_id`
- `tooth`: CHECK FDI permanente.
- `kind`: por ahora solo `tooth_status`.
- `value`: `present` o `absent`. Las piezas `uncertain` no se guardan como sugerencia, solo en el resultado del análisis.
- `confidence`: numeric(4,3).
- `evidence_positions` (smallint[]).
- `conflicts_with_record`, calculado al guardar el resultado.
- **Revisión:** `review_status` (`pending`, `accepted` o `rejected`), `reviewed_by_user_id`, `reviewed_at` y `applied_exam_revision`.
- **Restricciones:**
  - Único `(analysis_id, tooth, kind)`.
  - CHECK de coherencia: si está pendiente, los campos de revisión van nulos; si está decidida, van completos.

Las sugerencias y su decisión **no** se copian a `periodontal_exam_revisions`. La revisión del examen ya refleja lo aplicado y las tablas de IA conservan lo propuesto, de modo que se puede medir lo propuesto frente a lo aceptado (§7).

## 6. Estados y errores

```text
queued ──► running ──► completed
   │          │
   └──────────┴──────► failed (error_code)
```

| Estado | Significado |
| --- | --- |
| `queued` | Creado y en espera de ser enviado al servicio. |
| `running` | Enviado; se espera la respuesta. |
| `completed` | Resultado guardado; las sugerencias están en `pending`. Un análisis completo puede no tener sugerencias, por ejemplo si todas las piezas son `uncertain`. |
| `failed` | Terminó sin resultado. No se reintenta solo: el usuario pide un análisis nuevo. |

Códigos de `error_code` (la interfaz muestra el mensaje en español):

| Código | Causa | Mensaje |
| --- | --- | --- |
| `service_unavailable` | No hay conexión con el servicio o responde `503`. | «El servicio de análisis no está disponible. Puede llenar el periodontograma a mano.» |
| `timeout` | Sin respuesta en `AI_SERVICE_TIMEOUT_SECONDS` (120 s por defecto, a confirmar con las mediciones en CPU de ODON-266). | «El análisis tardó demasiado. Intente con menos fotos.» |
| `invalid_image` | El servicio respondió `413` o `415`. | «Alguna foto no se pudo analizar.» |
| `contract_mismatch` | La respuesta no valida contra el esquema o trae otra `contract_version`. | «El servicio de análisis no es compatible con esta versión de OdontoNet.» |
| `service_error` | El servicio respondió `500`, `400` o `401`: es un error de configuración, no del usuario. | «El análisis falló. Avise a administración.» |
| `interrupted` | La API se reinició con el análisis en `queued` o `running`. | «El análisis se interrumpió. Pídalo de nuevo.» |

- **Análisis abandonados:** al consultar o al pedir un análisis nuevo, uno en `queued` o `running` con más de dos veces el tiempo límite desde `created_at` pasa a `failed` con el código `interrupted`. Así un reinicio de la API no bloquea el examen para siempre (el índice único de §5).
- El backend valida la respuesta del servicio con esquemas Pydantic propios y **no** confía en ella: piezas fuera de FDI, índices de evidencia inexistentes o confianzas fuera de 0–1 producen el error `contract_mismatch`.
- Ningún error del servicio llega al navegador con su texto original; solo el código y el mensaje de esta tabla.

## 7. Plan de evaluación clínica

El objetivo es medir si la sugerencia ayuda, sin afirmar capacidad diagnóstica. **Los criterios de éxito numéricos se fijan con el asesor y quedan registrados aquí antes de abrir el conjunto de prueba.** Mientras no estén fijados, esta sección no contiene cifras de aceptación.

### 7.1 Preguntas

1. **Técnica, con datos públicos (ODON-266 y ODON-267):** calidad de la segmentación y numeración FDI de YOLO11s-seg frente a RF-DETR Seg en la misma partición. Se mide con mAP de máscara y exactitud de numeración por pieza y por vista. La latencia se mide en CPU.
2. **Clínica, con datos locales (ODON-272, tras el dictamen de ética de ODON-220):** concordancia entre la sugerencia de presencia o ausencia y el estado de la pieza registrado por el odontólogo al examinar al paciente.
3. **De uso (ODON-271 y ODON-272):** cuánto corrige el profesional: proporción de sugerencias aceptadas, rechazadas y aceptadas y luego editadas, y el tiempo para completar el estado dental con y sin sugerencias.

### 7.2 Diseño

- **Unidad de análisis:** posición dentaria por paciente (32 por paciente). La división desarrollo/prueba es **por paciente**, nunca por foto, para que las fotos de un mismo paciente no queden en ambos lados.
- **Referencia:**
  - Para la pregunta 2, el estado dental registrado en el examen clínico.
  - Para la anotación de fotos, el consenso de los dos odontólogos anotadores, reportando su acuerdo previo (kappa de Cohen) antes del consenso, porque no hay un tercer adjudicador.
- **Muestra prevista (plan de la épica):** 300 fotos de 60 pacientes en 5 vistas (30 de desarrollo y 30 de prueba bloqueada), con al menos 49 posiciones de pieza ausente en la prueba. El piso exploratorio es de 75 fotos de 15 pacientes. Son cifras de juicio propio porque no existe un mínimo publicado para esta tarea, y se presentan así.
- **Métricas de la pregunta 2:** sensibilidad y especificidad para «ausente», con intervalos de confianza del 95 % (método de Wilson). Se reportan por vista y por grupo de piezas (anteriores, premolares y molares), y aparte la proporción de `uncertain`.
- **Prueba bloqueada:** el conjunto de prueba no se mira hasta congelar el modelo, el umbral de operación y los criterios. Se evalúa **una vez**, y cualquier evaluación posterior se reporta como exploratoria.
- **Curva de aprendizaje:** se entrena con fracciones crecientes de los datos públicos y locales para sostener, o descartar, la hipótesis de que más datos mejoran el resultado. La hipótesis no se extiende al sondaje, que no es observable en la foto.
- **Tiempos:** se mide la latencia por análisis en un equipo equivalente al de la clínica, sin GPU. Si no hay acceso a uno, se usa una laptop con la GPU desactivada y se declara como aproximación.

### 7.3 Lo que no se afirma

- Que el sistema detecte enfermedad periodontal o la clasifique.
- Que la puntuación de confianza sea una probabilidad.
- Que los resultados obtenidos con datos públicos valgan para la población de la clínica antes de medirlos con datos locales.

## 8. Configuración

| Variable | Dónde | Uso |
| --- | --- | --- |
| `AI_SERVICE_URL` | backend | URL interna del servicio (p. ej. `http://ai-service:8001`). Si está vacía, la función está apagada. |
| `AI_SERVICE_TOKEN` | backend y ai-service | Secreto compartido. En producción, la API no arranca si la URL está definida y el secreto falta o es de ejemplo (como con el resto de secretos, decisión 22). |
| `AI_SERVICE_TIMEOUT_SECONDS` | backend | Tiempo límite por análisis (120 por defecto). |
| `AI_MODEL_PATH` | ai-service | Archivo de pesos, que se monta como volumen de solo lectura y no se versiona en Git. |

## 9. Compatibilidad y versiones

- `contract_version` es un entero en texto. Agregar campos opcionales no lo cambia; quitar campos, cambiar su significado o agregar estados sí.
- El backend acepta exactamente la versión que conoce. Un modelo nuevo con el mismo contrato solo cambia `model_version` y `weights_sha256`, y queda registrado en cada análisis.
