# Integración del servicio de IA — contrato v1

> Estado (2026-11-12): contrato v1 definido (ODON-250).
> - **Microservicio implementado y probado** (§3, ODON-269: `ai-service/service/`).
> - **Backend (§4–6, ODON-270) e interfaz de revisión (ODON-271): diseñados y revisados de forma independiente, sin implementar** (punto de cierre del proyecto del 2026-11-12). Cualquier cambio a este documento que rompa compatibilidad sube la versión del contrato.

## 1. Alcance y límites

- La IA es **asistencia**: propone valores y un profesional decide. Ninguna sugerencia entra al periodontograma sin que un profesional con perfil de doctor la acepte, y no hay aceptación automática. El sistema no emite diagnósticos ni clasifica la enfermedad.
- **Versión 1:** a partir de fotografías intraorales ya guardadas en el expediente, sugiere para cada pieza permanente FDI (11–48) si es **visible** o **no visible (probablemente ausente)**. La numeración FDI la produce el modelo de segmentación de dientes (ODON-267).
- **Qué significa «no visible»:** una foto no distingue una pieza ausente de una no erupcionada, retenida o reducida a raíz; esto ocurre sobre todo en los terceros molares (18, 28, 38 y 48). Marcar la pieza como ausente en el expediente es una decisión clínica: la interfaz presenta la sugerencia como «no visible en las fotos» y es el profesional quien la acepta como ausente.
- **Fuera de la versión 1:** sondaje, sangrado, supuración, nivel de inserción, movilidad y furcación no son observables en una fotografía y siguen siendo manuales. Recesión y placa son experimentos de tesis (ODON-274): se miden fuera de la interfaz y no se muestran como valores sugeridos.
- **Sin el servicio:** el periodontograma manual funciona igual. Si `AI_SERVICE_URL` está vacío, la interfaz oculta el botón para pedir análisis y la API responde `503` solo a esa petición. Los análisis ya guardados se pueden seguir consultando y revisando.

## 2. Componentes y flujo

```text
Navegador ──► API clínica (FastAPI) ──HTTP interno──► ai-service (CPU, sin internet)
                 │  lee las fotos de ImageStorage           │ no guarda nada
                 ▼                                           ▼
             PostgreSQL ◄── resultados y decisiones ──── respuesta JSON
```

1. **Pedido.** Un doctor o administración elige de 1 a 5 fotos del paciente desde un examen en **borrador** y pide el análisis.
2. **Envío.** La API crea el análisis en estado `queued`, responde `202` y lo procesa en segundo plano:
   - Lee cada original del almacenamiento privado.
   - Genera en memoria una copia reducida: JPEG con el lado mayor de 2048 px como máximo, sin metadatos.
   - Envía las copias al servicio.
3. **Resultado.** El servicio responde con detecciones por foto y un resultado por pieza. La API guarda las sugerencias y deja el análisis en `completed`, o en `failed` con un código de error.
4. **Revisión.** La interfaz consulta el estado y muestra las sugerencias junto a las fotos. Quien puede editar el borrador, con perfil de doctor (§4), acepta o rechaza cada sugerencia, y lo aceptado se aplica al borrador.

**Privacidad** (detalle en `PRIVACY.md`):
- **Datos que recibe el servicio:** solo la copia reducida de cada foto, su vista y un identificador opaco (UUID aleatorio por análisis) para correlacionar registros. Nunca nombre ni identificadores de paciente o de clínica.
- **Datos que conserva:** ninguna imagen; no escribe imágenes a disco ni registra su contenido, y sus registros solo contienen el UUID, los tiempos y los códigos de error.
- **Red:** escucha solo en la red interna de Docker. Caddy no lo publica y no tiene salida a internet.
- **Consentimiento:** pedir un análisis exige el mismo consentimiento vigente para fotografías (`granted`) que subir una foto. Si el paciente lo revocó, sus fotos no se envían.
- **Trazabilidad:** cada lectura de un original para enviarlo queda en `image_access_logs`, atribuida a quien pidió el análisis, como cualquier apertura del original (decisión 15).

## 3. API del servicio (`ai-service`)

El prefijo es `/v1` y el formato JSON en UTF-8. Los errores siguen un formato análogo al de la API clínica, con un código para la máquina: `{"detail": "<mensaje en español>", "code": "<código>"}`.

Cada petición, salvo `/health`, lleva la cabecera `X-Service-Token` con el secreto compartido `AI_SERVICE_TOKEN`. El servicio la compara en tiempo constante (`hmac.compare_digest`) y responde `401` si falta o no coincide.

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
  "limits": {"max_images": 5, "max_bytes_per_image": 10485760, "max_side_px": 4096},
  "device": "cpu"
}
```

- El nombre y la versión del modelo del ejemplo son ilustrativos.
- El backend guarda `model_name`, `model_version` y `weights_sha256` en cada análisis, para que cada resultado se pueda atribuir a un modelo exacto.
- La copia reducida que envía el backend (JPEG con el lado mayor de 2048 px como máximo) queda siempre dentro de estos límites, sea cual sea el tamaño del original guardado.

### `POST /v1/analyses/tooth-status`

`multipart/form-data`:

| Campo | Tipo | Regla |
| --- | --- | --- |
| `request_id` | UUID | Obligatorio; aleatorio, sin relación con ids de la base. |
| `images` | archivo, 1–5 | JPEG. |
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
      "width": 2048, "height": 1536,
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

- **Coordenadas:** normalizadas a 0–1 respecto a la imagen. `bbox` es `[x1, y1, x2, y2]` y `polygon` es el contorno simplificado de la máscara, con 64 puntos como máximo.
- **`teeth`:** trae siempre las 32 piezas.
  - `status` vale `present` (visible), `absent` (no visible donde la zona sí se ve) o `uncertain`.
  - `uncertain` aparece cuando ninguna vista muestra la zona con calidad suficiente o la confianza queda bajo el umbral de operación. Nunca se convierte en sugerencia.
- **`evidence`:** índices de las fotos que sustentan el resultado. Para `absent`, son las fotos donde la zona era visible y no se detectó la pieza.
- **`confidence`:** es la puntuación del modelo, no una probabilidad calibrada. La interfaz no la presenta como porcentaje de acierto.
- **`quality`:** una foto con `quality.usable = false` (motivos como `blurred`, `too_dark` o `no_teeth_detected`) queda excluida del resultado por pieza, sin hacer fallar el análisis.

Errores del servicio:

| HTTP | `code` | Cuándo |
| --- | --- | --- |
| 400 | `invalid_request` | Faltan campos, `views` no coincide con `images` o una vista es desconocida. |
| 401 | `unauthorized` | Falta `X-Service-Token` o no coincide. |
| 413 | `image_too_large` | Una foto supera los límites de `/v1/model` (no debería ocurrir con la copia reducida). |
| 415 | `unsupported_image` | El contenido no es una imagen admitida. |
| 503 | `model_not_ready` | El modelo aún no está cargado. |
| 500 | `inference_error` | Fallo interno, sin trazas en la respuesta. |

## 4. API clínica (backend)

Las rutas cuelgan de `/patients/{patient_id}/periodontal-exams/{exam_id}/ai-analyses` y usan la clínica del token, como en todo el sistema.

| Ruta | Admin | Doctor | Recepción | Descripción |
| --- | --- | --- | --- | --- |
| `POST .../ai-analyses` | ✅ | ✅ | ⛔ 403 | Pide un análisis. Cuerpo `{"image_ids": [1–5 ids]}`. Responde `202` con el análisis en `queued`. |
| `GET .../ai-analyses` | ✅ | ✅ | ⛔ 403 | Análisis del examen, el más reciente primero. Funciona aunque el servicio esté apagado. |
| `GET .../ai-analyses/{analysis_id}` | ✅ | ✅ | ⛔ 403 | Estado, fotos, modelo y sugerencias, con `conflicts_with_record` calculado sobre el borrador vigente. |
| `POST .../ai-analyses/{analysis_id}/review` | ✅* | ✅* | ⛔ 403 | Acepta o rechaza sugerencias (ver 4.2). |

\* **Quién revisa:** se combinan dos reglas:

- **La del periodontograma:** solo quien registró el examen, o administración, guarda el borrador (decisión 16).
- **La del plan de la épica:** solo un profesional con perfil de doctor acepta sugerencias.

Por eso revisa quien puede guardar el borrador **y** tiene perfil de doctor: el doctor autor del examen, o un usuario `admin` con perfil de doctor. Cualquier otro usuario recibe `403`. Un `admin` sin perfil de doctor puede pedir y ver análisis, pero no decidir sobre las sugerencias.

Las ediciones manuales que administración hace con el guardado normal siguen permitidas: son registros propios del profesional, no aceptación de una sugerencia. Lo que esta regla garantiza es que toda sugerencia aceptada tenga un doctor identificado como responsable. Al implementarla, ODON-270 actualiza `PERMISSIONS.md` y la matriz del frontend.

### 4.1 Reglas al pedir un análisis

- **`404`** si el paciente, el examen o alguna foto no existen, son de otra clínica, o si el examen o las fotos pertenecen a otro paciente.
- **`422`** si `image_ids` está vacío, tiene más de 5 elementos o repetidos, o si alguna foto está anulada.
- **`409`** en estos casos:
  - El examen no es un borrador vigente: está finalizado o anulado.
  - El paciente está archivado.
  - El paciente no tiene un consentimiento vigente para fotografías.
  - Ya hay un análisis `queued` o `running` para ese examen; la respuesta incluye `current_analysis_id`.
- **`503`** si `AI_SERVICE_URL` está vacío. El mensaje dice que el análisis automático no está disponible y que el periodontograma se puede llenar a mano.
- **Revisión base:** el análisis guarda la revisión del examen al momento de pedirlo (`exam_revision`). Sirve para la evaluación (§7) y para saber qué cambió después.
- **Auditoría:** el pedido queda registrado como `ai_analysis.requested`, solo con ids.

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

- **Concurrencia:** la revisión bloquea el examen (`SELECT … FOR UPDATE`, como el guardado del borrador) y compara `base_revision` con la revisión vigente. Si no coinciden, la API responde `409` con `current_revision`.
- **Una sola decisión:** cada sugerencia se decide **una sola vez**, de `pending` a `accepted` o a `rejected`. Si ya estaba decidida, la API responde `409`.
- **Efecto de aceptar** (en la misma transacción que la revisión):
  - `absent` marca la pieza como ausente y vacía sus mediciones, su movilidad y su furcación, igual que hacerlo a mano. Si era un implante, deja de serlo, porque la base no admite una pieza ausente que sea implante.
  - `present` en una pieza marcada ausente la desmarca, sin mediciones.
  - `present` en una pieza ya presente no cambia nada.
- **Revisiones del examen:**
  - Si lo aceptado cambia algo, se crea **una** revisión nueva del examen.
  - Si no cambia nada (solo rechazos, o aceptaciones sin efecto), no se crea revisión, como en un guardado sin cambios, y la respuesta devuelve la revisión vigente.
  - Cada sugerencia aceptada que produjo un cambio guarda la revisión que la aplicó (`applied_exam_revision`).
- **Origen:** el origen de la decisión queda **solo en las tablas de IA**. En el periodontograma, `periodontal_teeth.source` hoy registra el origen de la movilidad (ODON-262) y no se toca: lo aceptado se escribe como un registro manual del profesional que lo aceptó.

  Lo que propuso la IA se reconstruye cruzando `ai_suggestions` (sugerencia, decisión, quién y en qué revisión) con `periodontal_exam_revisions`. Así no hace falta ampliar el CHECK de `source` ni el de la movilidad predeterminada (`ck_periodontal_teeth_default_mobility`).
- **Conflicto con lo registrado (`conflicts_with_record`):** se calcula **al consultar y al revisar**, siempre sobre el borrador vigente y con el examen bloqueado durante la revisión. Nunca se guarda fijo. Una sugerencia está en conflicto si aceptarla cambiaría la pieza y además se cumple alguna de estas condiciones:
  - La sugerencia es `present` y la pieza está marcada como ausente. Marcar una ausencia es siempre un acto explícito, manual o copiado del examen anterior.
  - La pieza tiene algún dato registrado: algún valor por sitio, movilidad, furcación o nota.
  - La pieza es un implante.

  En la práctica, la única aceptación sin conflicto es `absent` sobre una pieza presente, natural y sin datos.
- **«Aceptar todas»:**
  - Envía todas las sugerencias pendientes que no estén en conflicto según la última consulta.
  - La API vuelve a calcular el conflicto bajo bloqueo y responde `409` si alguna de las enviadas como «todas» ya está en conflicto. Para eso la petición lleva `"bulk": true`. La interfaz recarga y vuelve a mostrar las sugerencias.
  - Existe solo para presente/ausente: los tipos que se agreguen después se revisan uno por uno.
- **Aceptación individual de una sugerencia en conflicto:** se permite después de que la interfaz pida confirmación y diga qué datos se vaciarán.
- **Examen cerrado:** si el examen dejó de ser borrador vigente (finalizado o anulado), la revisión responde `409` y las sugerencias quedan `pending` para siempre, como registro.
- **Auditoría:** la revisión queda registrada como `ai_suggestions.reviewed`, con ids y el número de sugerencias aceptadas y rechazadas.

## 5. Modelo de datos (migración de ODON-270)

Las tablas siguen los patrones existentes: FKs compuestas con `clinic_id` (decisión 1), FKs triples para que todo sea del mismo paciente (como `fk_patient_images_consent`), nada se borra y las decisiones solo avanzan.

**`ai_analyses`**

- **Identificación y vínculos:**
  - `id` y `clinic_id`, con `UNIQUE (id, clinic_id)` y `UNIQUE (id, patient_id, clinic_id)` para las FKs de las tablas hijas.
  - `patient_id`.
  - `exam_id`, con FK triple `(exam_id, patient_id, clinic_id)` → `periodontal_exams(id, patient_id, clinic_id)`. Hoy `periodontal_exams` solo tiene `UNIQUE (id, clinic_id)`; la migración agrega el único `(id, patient_id, clinic_id)`.
  - `exam_revision`: la revisión del examen al pedir el análisis.
  - `request_uuid`: único.
- **Estado y autor:**
  - `status`: CHECK con los estados de §6.
  - `requested_by_user_id`, con FK compuesta a `users(id, clinic_id)`.
- **Modelo y contrato:** `contract_version`, `model_name`, `model_version` y `weights_sha256`, todos nulos hasta que el servicio responde.
- **Resultado:** `elapsed_ms` y `error_code`. `error_code` es obligatorio si `status = 'failed'` y nulo en cualquier otro estado.
- **Tiempos:** `created_at`, `started_at` y `finished_at`.
- **Índices:**
  - Índice único parcial sobre `exam_id` con la condición `WHERE status IN ('queued','running')`, que garantiza en la base un solo análisis activo por examen.
  - Índice sobre `(clinic_id, exam_id)`.

**`ai_analysis_images`**

- `clinic_id`, `patient_id`, `analysis_id` e `image_id`, con dos FKs triples: `(analysis_id, patient_id, clinic_id)` → `ai_analyses` y `(image_id, patient_id, clinic_id)` → `patient_images` (la migración agrega en `patient_images` el único `(id, patient_id, clinic_id)`, que hoy no existe).
- `position` (0–4) y la `view` usada en ese momento: las fotos pueden corregir su vista después, y una foto sin vista se guarda como `other`, igual que se envió.
- `usable` y `quality_reasons` (texto[]).
- `detections` (JSONB): la lista tal como la devolvió el servicio, con coordenadas normalizadas y sin píxeles.
- Únicos `(analysis_id, position)` y `(analysis_id, image_id)`.

**`ai_suggestions`**

- `clinic_id` y `analysis_id`, con FK compuesta `(analysis_id, clinic_id)` → `ai_analyses`.
- `tooth`: CHECK FDI permanente.
- `kind`: por ahora solo `tooth_status`.
- `value`: `present` o `absent`. Las piezas `uncertain` no se guardan como sugerencia: quedan solo en `detections` y en la respuesta.
- `confidence`: numeric(4,3).
- `evidence_positions` (smallint[]).
- **Revisión:**
  - `review_status`: `pending`, `accepted` o `rejected`.
  - `reviewed_by_user_id`, con FK compuesta a `users(id, clinic_id)`.
  - `reviewed_at` y `applied_exam_revision`.
- **Restricciones:**
  - Único `(analysis_id, tooth, kind)`.
  - Coherencia de la revisión:
    - Pendiente: `reviewed_by_user_id`, `reviewed_at` y `applied_exam_revision` nulos.
    - Decidida: `reviewed_by_user_id` y `reviewed_at` obligatorios.
    - Rechazada: `applied_exam_revision` nulo.
    - Aceptada: `applied_exam_revision` es nulo solo si la aceptación no cambió nada.

Las sugerencias y su decisión **no** se copian a `periodontal_exam_revisions`. La revisión del examen refleja lo aplicado y las tablas de IA conservan lo propuesto, de modo que se puede medir lo propuesto frente a lo aceptado (§7).

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
| `timeout` | Sin respuesta en `AI_SERVICE_TIMEOUT_SECONDS` (120 s por defecto; ODON-266 midió en CPU un p95 por foto inferior a 1 s, así que 5 fotos quedan muy por debajo, ver `ai-service/docs/viabilidad.md`). | «El análisis tardó demasiado. Intente con menos fotos.» |
| `invalid_image` | El servicio respondió `413` o `415`, o un original no se pudo leer del almacenamiento. | «Alguna foto no se pudo analizar.» |
| `contract_mismatch` | La respuesta no valida contra el esquema o trae otra `contract_version`. | «El servicio de análisis no es compatible con esta versión de OdontoNet.» |
| `service_error` | El servicio respondió `500`, `400` o `401`: es un error de configuración, no del usuario. | «El análisis falló. Avise a administración.» |
| `interrupted` | La API se reinició con el análisis en `queued` o `running`. | «El análisis se interrumpió. Pídalo de nuevo.» |

**Concurrencia y ejecución:**

- **Segundo plano:** la tarea corre en la propia API (`BackgroundTasks` de FastAPI) con **su propia sesión de base**, nunca la de la petición. No hace falta una cola externa para un servidor de una sola clínica.
- **Transiciones condicionadas:** cada cambio de estado es un `UPDATE … WHERE id = :id AND status = :esperado`; si no afecta ninguna fila, la tarea se detiene sin escribir nada. Así, si un análisis ya se marcó `interrupted`, una respuesta tardía del servicio se descarta y no crea sugerencias.
- **Al guardar el resultado:** se escribe en una sola transacción el paso de `running` a `completed`, junto con las fotos analizadas y las sugerencias. Si para entonces el examen ya no es un borrador vigente, el resultado se guarda igual (como registro) y la revisión responderá `409` (§4.2).
- **Análisis abandonados:** al consultar o al pedir un análisis nuevo, se marcan `failed` con el código `interrupted`:
  - uno en `queued` con más de dos veces el tiempo límite desde `created_at`;
  - uno en `running` con más de dos veces el tiempo límite desde `started_at`.

  Así un reinicio de la API no bloquea el examen para siempre (por el índice único de §5).
- **Auditoría:** las transiciones automáticas no generan eventos en `audit_events`, que exigen un usuario como actor; quedan en los tiempos y el estado de `ai_analyses`. Sí se auditan el pedido y la revisión, que hace una persona.
- **Validación del resultado:** el backend valida la respuesta del servicio con esquemas Pydantic propios que **ignoran campos desconocidos** (para que un campo opcional nuevo no rompa la versión, §9) y **no** confía en ella. Piezas fuera de FDI, índices de evidencia inexistentes o confianzas fuera de 0–1 producen el error `contract_mismatch`.
- **Mensajes:** ningún error del servicio llega al navegador con su texto original; solo el código y el mensaje de esta tabla.

## 7. Plan de evaluación clínica

El objetivo es medir si la sugerencia ayuda, sin afirmar capacidad diagnóstica. **Los criterios de éxito numéricos se fijan y quedan registrados aquí antes de abrir el conjunto de prueba** (§7.3 para la pregunta 1; los de las preguntas 2 y 3 quedan pendientes hasta ODON-272).

### 7.1 Preguntas

1. **Técnica, con datos públicos (ODON-266 y ODON-267):** calidad de la segmentación y numeración FDI de YOLO11s-seg frente a RF-DETR Seg en la misma partición. Se mide con mAP de máscara y exactitud de numeración por pieza y por vista. La latencia se mide en CPU.
2. **Clínica, con datos locales (ODON-272, tras el dictamen de ética de ODON-220):** concordancia entre la sugerencia «visible / no visible» y el estado de la pieza registrado por el odontólogo al examinar al paciente.
3. **De uso (ODON-271 y ODON-272):** cuánto corrige el profesional: proporción de sugerencias aceptadas y rechazadas, y de las aceptadas que se editan después; y el tiempo para completar el estado dental con y sin sugerencias.

### 7.2 Diseño

- **Unidad de análisis:** posición dentaria por paciente (32 por paciente). La división desarrollo/prueba es **por paciente**, nunca por foto, para que las fotos de un mismo paciente no queden en ambos lados.
- **Referencia:**
  - **Pregunta 2:** el estado dental que el odontólogo registra en el examen **antes** de pedir el análisis, es decir, la revisión guardada en `exam_revision`. Así la referencia no puede incluir sugerencias aceptadas de la propia IA, lo que evita el sesgo de incorporación. El protocolo pide completar el estado dental antes de pedir el análisis.
  - **Anotación de fotos:** el consenso de los dos odontólogos anotadores, reportando su acuerdo previo (kappa de Cohen) antes del consenso, porque no hay un tercer adjudicador.
- **Muestra prevista (plan de la épica):** 300 fotos de 60 pacientes en 5 vistas (30 pacientes de desarrollo y 30 de prueba bloqueada), con al menos 49 posiciones de pieza ausente en la prueba. El piso exploratorio es de 75 fotos de 15 pacientes. Son cifras de juicio propio porque no existe un mínimo publicado para esta tarea, y se presentan así.
- **Métricas de la pregunta 2:** sensibilidad y especificidad para «no visible» frente a «ausente», con intervalos de confianza del 95 % calculados con **bootstrap por paciente**: las 32 posiciones de un paciente no son independientes, y un intervalo que las trate como tales saldría demasiado estrecho. Se reportan por vista y por grupo de piezas (anteriores, premolares, molares y terceros molares aparte), además de la proporción de `uncertain`.
- **Prueba bloqueada:** el conjunto de prueba no se mira hasta congelar el modelo, el umbral de operación y los criterios. Se evalúa **una vez**, y cualquier evaluación posterior se reporta como exploratoria.
- **Curva de aprendizaje:** se entrena con fracciones crecientes de los datos públicos y locales para sostener, o descartar, la hipótesis de que más datos mejoran el resultado. La hipótesis no se extiende al sondaje, que no es observable en la foto.
- **Tiempos:** se mide la latencia por análisis (hasta 5 fotos) en un equipo equivalente al de la clínica, sin GPU. ODON-266 midió la latencia por foto; la del análisis completo se mide con el servicio de ODON-269. Si no hay acceso a uno, se usa una laptop con la GPU desactivada y se declara como aproximación.
- **Datos de pacientes en la evaluación:** solo entran pacientes con autorización de uso en investigación (`research_use`) y con el dictamen de ética aprobado. Los registros de `ai_*` de los demás pacientes son parte de su expediente y no se usan para medir.

### 7.3 Criterio de la pregunta 1 (fijado el 2026-11-12, antes de evaluar)

Decisión del desarrollador para ODON-267, registrada antes de usar el conjunto de prueba de IOP-Compass.

- **Medida:** presencia por pieza y paciente. Una pieza cuenta como «visible» si el modelo la detecta en al menos una de las 5 vistas. La referencia es la anotación de IOP-Compass: visible si está anotada en alguna vista. La clase de interés es **«no visible»**.
- **Población del criterio principal:** las 28 piezas 11–47, **sin terceros molares**. Los terceros molares se informan aparte: en ese conjunto la mayoría no son visibles (320 de 400 posiciones de prueba), una situación distinta.
- **Umbral de operación:** se elige **solo con validación** (200 pacientes) y queda congelado, junto con los pesos, antes de evaluar en prueba.
- **Criterio (modelo principal, YOLO11s-seg, conjunto de prueba de 100 pacientes):** **sensibilidad de «no visible» ≥ 0,80 y especificidad ≥ 0,95**, como estimaciones puntuales, informadas con IC 95 % por bootstrap por paciente.
- **Por qué pesa más la especificidad:** un «no visible» falso, si el doctor lo acepta, vacía las mediciones de una pieza presente. Uno que se escapa deja la tarea al doctor, como sin IA.
- **Precisión esperada:** el conjunto de prueba tiene 30 posiciones no visibles sin terceros molares, de 2800. La sensibilidad tendrá un intervalo amplio, de unos ±15 puntos, y así se informa.
- **Descriptivo, sin umbral:** mAP de máscara y exactitud de numeración por vista; terceros molares; curva de aprendizaje de YOLO.
- **Cambios de alcance del 2026-11-12, registrados antes de ver resultados de la curva** (para cerrar el proyecto en el día):
  - **Curva de aprendizaje reducida:** 25, 50 y 100 % de los pacientes de entrenamiento × semillas 0 y 1, todas con 30 épocas, para que sean comparables entre sí. El modelo principal ya estaba en meseta hacia la época 25 (mAP50-95 de máscara en validación 0,863 frente a 0,873 de la mejor época). Cada corrida congela su umbral en su propia validación y se evalúa una vez en prueba.
  - **Comparación con RF-DETR Seg Small, a trabajo futuro:** completa costaría unas 40 h de GPU. La viabilidad ya medida en ODON-266 (entrena en una GPU de 6 GB y llega a mAP50 de máscara 0,80 tras una época) queda como antecedente.
- **Comportamiento del servicio a partir de los resultados** (ODON-269): los terceros molares nunca se sugieren como «no visible», porque su especificidad en prueba fue 0,41.
- **Si no se cumple:** se informa como resultado. No se cambia el modelo, el umbral ni el criterio mirando el conjunto de prueba.
- **Alcance:** mide la visibilidad en fotos públicas frente a una anotación, no la ausencia clínica (pregunta 2).

### 7.4 Lo que no se afirma

- Que el sistema detecte enfermedad periodontal o la clasifique.
- Que «no visible» equivalga a «ausente»: esa equivalencia la decide el profesional.
- Que la puntuación de confianza sea una probabilidad.
- Que los resultados obtenidos con datos públicos valgan para la población de la clínica antes de medirlos con datos locales.

## 8. Configuración

| Variable | Dónde | Uso |
| --- | --- | --- |
| `AI_SERVICE_URL` | backend | URL interna del servicio (p. ej. `http://ai-service:8001`). Si está vacía, la función está apagada. |
| `AI_SERVICE_TOKEN` | backend y ai-service | Secreto compartido. En producción, la API no arranca si la URL está definida y el secreto falta o es de ejemplo (como con el resto de secretos, decisión 22). |
| `AI_SERVICE_TIMEOUT_SECONDS` | backend | Tiempo límite por análisis (120 por defecto). |
| `AI_MODEL_PATH` | ai-service | Archivo de pesos, que se monta como volumen de solo lectura y no se versiona en Git. |
| `AI_MODEL_META` | ai-service | `meta.json` junto a los pesos (ODON-269): versión, SHA-256 que deben tener los pesos, umbral congelado en validación, margen de `uncertain`, cobertura por vista y piezas que nunca son `absent`. Lo genera `research/export_model.py`. |

## 9. Compatibilidad y versiones

- `contract_version` es un entero en texto.
  - **No la cambian** los campos opcionales nuevos: los esquemas del backend ignoran campos desconocidos.
  - **Sí la cambian** quitar campos, cambiar su significado o agregar estados.
- El backend acepta exactamente la versión que conoce. Un modelo nuevo con el mismo contrato solo cambia `model_version` y `weights_sha256`, y queda registrado en cada análisis.
