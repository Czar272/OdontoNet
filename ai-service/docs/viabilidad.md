# Viabilidad técnica y datos públicos (ODON-266)

> Etapa 0 del plan de ODON-13. Estado: **completa** (2026-11-11), salvo la medición en el equipo real de la clínica. Este documento no contiene datos de pacientes ni imágenes: solo conteos, tiempos y procedencia.

## 1. Criterio fijado antes de medir

Decisión del desarrollador, el 2026-11-11, antes de la primera medición: **≤ 10 s por foto en el percentil 95, en CPU y sin GPU**. Con 5 fotos son unos 50 s, dentro del tiempo límite de 120 s del contrato (`docs/AI_INTEGRATION.md`, §6).

**Qué incluye el tiempo:** preprocesado, inferencia y posprocesado del modelo para una foto ya decodificada en memoria (BGR), reducida a 2048 px de lado mayor, el tamaño de la copia que envía el backend.

**Qué no incluye:**
- Decodificar el JPEG recibido (unas decenas de ms).
- Agregar los resultados por pieza en las 5 vistas.
- Llevar las máscaras de YOLO al tamaño de la foto: usa `retina_masks=False`, mientras que la ruta ONNX de RF-DETR sí las reescala.

Por eso la latencia por análisis se medirá con el servicio completo (ODON-269).

## 2. Equipo de medición

| Elemento | Valor |
| --- | --- |
| CPU | 12th Gen Intel Core i7-12650H (10 núcleos físicos, 16 lógicos) |
| RAM | 15,7 GB |
| GPU | NVIDIA RTX 4050 Laptop, 6 GB. Solo para entrenar. Al medir se oculta con `CUDA_VISIBLE_DEVICES=-1` (en Windows, `""` borra la variable en vez de ocultarla), y el script se detiene si `torch.cuda.is_available()` sigue siendo verdadero. Los 18 JSON registran `cuda_visible: false`. |
| Sistema | Windows 11, Python 3.12 |
| Energía al medir | **Con batería** (26 %, descargando), plan «Equilibrado»: la CPU trabaja por debajo de su frecuencia máxima. Las cifras son conservadoras frente a un equipo de escritorio conectado a la corriente. |

No es el equipo de la clínica: es una **aproximación**. Para acercarse a un equipo más modesto se repite cada medición restringida a 4 y a 2 núcleos físicos (afinidad de CPU, §3). Los núcleos elegidos son de rendimiento (P), sin su par SMT. En ese sentido la aproximación es **optimista** frente a una CPU de oficina antigua, y la batería la compensa en parte. La medición en el equipo real queda pendiente para cuando haya acceso.

## 3. Latencia en CPU

Comando: `bash research/run_latency.sh [carpeta_de_fotos]`. Hace 50 repeticiones tras 5 de calentamiento y deja el JSON de cada medición en `results/latencia/`.

**Medición válida (2026-11-11), con fotos reales:** las 5 vistas de 4 pacientes del conjunto de prueba de IOP-Compass (20 fotos), reducidas a 2048 px, con el equipo sin otras tareas. 50 repeticiones tras 5 de calentamiento.

**Cómo se limitan los núcleos.** «4 núcleos» y «2 núcleos» **restringen el proceso entero con afinidad de CPU** a 4 o 2 núcleos físicos distintos. Además se fijan los hilos de PyTorch y de ONNX Runtime, y se parchea `NUM_THREADS` de Ultralytics, porque su `select_device()` vuelve a poner 8 hilos de PyTorch en cada `predict`. Cada JSON registra `torch_threads_max_seen`, que coincide con el límite en todas las mediciones restringidas. Sin estas correcciones, una corrida anterior llegó a 3,6 s por foto por la saturación de hilos, y se descartó.

**Memoria:** «Pico de memoria» es el pico real del proceso (`peak_wset` de Windows), en GiB.

| Modelo | Motor | 10 núcleos p50 / p95 | 4 núcleos p50 / p95 | 2 núcleos p50 / p95 | Pico de memoria |
| --- | --- | --- | --- | --- | --- |
| YOLO11s-seg (640) | PyTorch | 0,17 / 0,25 s | 0,16 / 0,25 s | 0,41 / 0,57 s | 1,02 GiB |
| YOLO11s-seg (640) | ONNX Runtime | 0,17 / 0,20 s | 0,60 / 0,63 s | 0,65 / 0,75 s | 1,21 GiB |
| RF-DETR Seg Nano (312) | PyTorch | 0,47 / 0,52 s | 0,41 / 0,48 s | 0,99 / 1,11 s | 1,17 GiB |
| RF-DETR Seg Nano (312) | ONNX Runtime | 0,35 / 0,39 s | 0,34 / 0,39 s | 0,46 / 0,51 s | 1,26 GiB |
| RF-DETR Seg Small (384) | PyTorch | 0,65 / 0,77 s | 0,55 / 0,61 s | 0,85 / 1,10 s | 1,19 GiB |
| RF-DETR Seg Small (384) | ONNX Runtime | 0,49 / 0,52 s | 0,45 / 0,66 s | 0,70 / 0,78 s | 1,28 GiB |

**Lectura:**
- El peor caso es un **p95 de 1,11 s (RF-DETR Seg Nano (312), PyTorch, 2 núcleos)**, unas 9 veces por debajo del umbral de 10 s, con batería y 2 núcleos. Con 5 fotos, la inferencia de un análisis completo quedaría por debajo de unos 6 s incluso así.
- El pico de memoria por proceso es de 1,0–1,3 GiB.
- Hay variación de unas décimas entre configuraciones, a veces con menos núcleos más rápido que con todos, por la frecuencia variable con batería. Como diferencia entre motores, no es concluyente. Se elegirá el motor según la medición en el equipo real.
- **Pendiente:** medir en el equipo de la clínica, conectado a la corriente.

Las mediciones previas se descartaron por tres razones: coincidieron con otra tarea pesada, tenían el límite de hilos defectuoso y no ocultaban la GPU. Los JSON con fotos sintéticas se conservan en `results/latencia/*-sintetica.json` solo como registro.

## 4. Entrenamiento en la RTX 4050 (6 GB)

Entrenamiento corto con precisión mixta, primero con datos sintéticos (`research/make_synthetic.py`: 160 imágenes de 1280×960 con 14–28 instancias de 32 clases), para medir VRAM y tiempo. La memoria depende del tamaño de imagen, del lote y del número de instancias, no del contenido. Comando: `research/train_smoke.py`; resultados en `results/entrenamiento-sintetico/`.

| Modelo | Resolución | Lote (acumulación) | VRAM asignada / reservada máx. | Tiempo por época (160 imágenes) |
| --- | --- | --- | --- | --- |
| YOLO11s-seg | 640 | 8 (1) | 2,70 / 3,19 GiB | 44 s (2 épocas) |
| RF-DETR Seg Small | 384 | 2 (4) | 3,11 / 3,73 GiB | 244 s (1 época, con evaluación) |

**Con IOP-Compass (2026-11-11):** 3500 fotos de entrenamiento y 1000 de validación de la partición por paciente, reducidas a 1280 px. Resultados en `results/entrenamiento-iop/`.

| Modelo | Épocas | Lote (acumulación) | VRAM asignada / reservada máx. | Tiempo por época | mAP50 / mAP50-95 de máscara en validación |
| --- | --- | --- | --- | --- | --- |
| YOLO11s-seg | 3 | 8 (1) | 2,70 / 3,03 GiB | ~2 min (122 s) | época 1: 0,83 / 0,75 → época 3: **0,91 / 0,82** |
| RF-DETR Seg Small | 1 | 2 (4) | 3,24 / 4,12 GiB | ~17 min (1039 s) | época 1: **0,80 / 0,73** |

**Por pieza (YOLO, época 3, validación):** mAP50 de máscara de 0,96 de media en las 28 piezas que no son terceros molares, ninguna por debajo de 0,92. En los terceros molares baja a 0,70 (18), 0,69 (28), 0,35 (38) y 0,55 (48), coherente con que tienen unas 10 veces menos ejemplos (§5.1). Detalle en `results/entrenamiento-iop/yolo11s-seg-por-pieza-val.json`, generado con `research/val_per_class.py`. Las métricas por época están en `results/entrenamiento-iop/yolo11s-seg.json` (`per_epoch`).

**Lectura:**
- Los dos modelos entrenan en la RTX 4050 con margen de VRAM.
- Que el mAP suba **no** prueba que las etiquetas estén bien, porque un error sistemático también se aprende. Las etiquetas FDI se comprobaron aparte, de forma geométrica (§5.1): en el 100 % de las fotos frontales la 11 queda a la izquierda de la 21 en la imagen (968 fotos) y por encima de la 41 (967 fotos). La correspondencia FDI → clase la cubren las pruebas.
- RF-DETR es unas 8,5 veces más lento por época. 50 épocas serían unas 14 h, que es lo que justifica llevar el comparador y la curva de aprendizaje a una GPU en la nube (plan de ODON-267). YOLO, con 100 épocas, son unas 3,5 h en local.
- **Advertencia:** son cifras de una prueba corta sobre **validación**, no resultados del modelo. El conjunto de prueba (100 pacientes) sigue sin usar y se evalúa una sola vez en ODON-267, con el umbral y los criterios ya fijados. Estas cifras miden la segmentación y numeración en fotos públicas, no la capacidad de decidir si una pieza está ausente en un paciente, que se evalúa con datos clínicos (`docs/AI_INTEGRATION.md`, §7).

En Windows, RF-DETR (Lightning) necesita `PYTHONUTF8=1`: sin eso falla al escribir en la consola cp1252.

**Decisión metodológica: sin volteo horizontal.** Ultralytics (`fliplr=0.5`) y RF-DETR (`HorizontalFlip p=0.5`) voltean las imágenes por defecto. En una foto dental el espejo cambia el cuadrante, por ejemplo la 16 por la 26, sin cambiar la etiqueta, así que el modelo aprendería números FDI falsos. Se desactiva en los dos (`fliplr=0.0` y `aug_config={}`). Para usar el volteo habría que reasignar las etiquetas de cada cuadrante.

## 5. Datos públicos

### 5.1 IOP-Compass

Descargado con cuenta propia el 2026-11-11 (zip de 44,2 GB), y auditado con `research/audit_iop.py` → `results/auditoria-iop.json`.

**Contenido verificado:**
- **1000 pacientes × 5 vistas** (Center, Left, Right, Upper, Down): 5000 PNG y 5000 JSON, sin ninguno faltante.
- **Formato del JSON:** lista `teeth` con, por pieza, `FDI_NUM`, contornos en píxeles (`contours`), caja, área, centroide y arcada. Son **contornos (máscaras poligonales), no solo cajas**.
- **Etiquetas:** 88 601 piezas, todas con FDI permanente válido (11–48). Ninguna etiqueta queda sin reconocer y todas tienen polígono. 33 piezas tienen más de un contorno; se conserva el mayor.
- **Piezas por vista:** frontal 26 078, laterales 17 887 (izquierda) y 17 487 (derecha), oclusales 13 587 (superior) y 13 562 (inferior).
- **Terceros molares (18, 28, 38, 48):** entre 199 y 281 instancias cada uno, frente a unas 2400–4000 del resto. Aparecen en 360 pacientes. Son clases minoritarias y hay que reportarlas aparte.
- **Piezas por paciente:** entre 24 y 32 visibles en alguna vista (media 28,5). Hay 3523 posiciones no visibles en ninguna vista. «No visible» no equivale a «ausente»: incluye terceros molares no erupcionados.
- **Lado de las vistas laterales:** es el **del paciente**. En «Left» predominan los cuadrantes 2 y 3 (37 % y 37 %) y en «Right» el 1 y el 4 (38 % y 38 %). Coincide con `left_lateral` y `right_lateral` de OdontoNet. Las proporciones por vista están en `quadrant_share_by_view` de la auditoría.
- **Coherencia geométrica de las etiquetas:** en la vista frontal la 11 aparece a la izquierda de la 21 en la imagen en el 100 % de las 968 fotos con ambas, y por encima de la 41 en el 100 % de 967 (`label_consistency`).
- **Nombres de archivo:** las imágenes se llaman `IOP_<Vista>_<pid>.png`, sin `RawImage_` como en la configuración del repositorio. El lector acepta ambos.

**Partición:** por paciente, con semilla 42: 700 de entrenamiento, 200 de validación y 100 de prueba (`results/particion-iop.json`). No es la partición de los autores. Para comparar con sus resultados publicados habría que usar la suya.

### 5.2 Otros revisados

| Dataset | Uso en ODON-13 | Motivo |
| --- | --- | --- |
| COde (zirak-ai) | Solo una revisión exploratoria de «no visible» | Fotos de 448 px, sin máscaras; texto clínico por control; 245 pacientes repetidos entre entrenamiento y prueba (auditoría en `results/auditoria-code.json`) |
| MIO | Revisión visual del cambio de dominio | Latinoamericano (México), pero sin FDI; una etiqueta por foto |
| Gingivitis MGI (Mendeley) | Candidato para ODON-274 | Inflamación visual de 12 dientes anteriores; no equivale al sangrado al sondaje |
| MouthCare | No | Su licencia prohíbe entrenar modelos para investigación publicada |
| Catálogo de Uribe | No | Ningún dataset con piezas FDI en fotos |

## 6. Procedencia de cada componente

Ningún dataset, peso ni modelo exportado entra a Git (`.gitignore`: `ai-service/weights/`, `ai-service/runs/`, `*.pt`, `*.onnx`). Los datasets viven en `Datasets_Odontonet/`, junto al repositorio.

| Componente | Versión | Origen | Hash | Licencia de código | Licencia de pesos o datos |
| --- | --- | --- | --- | --- | --- |
| PyTorch / torchvision | 2.14.1 / 0.29.1 (+cu130) | download.pytorch.org | wheel oficial | BSD-3 y otras (metadatos del paquete) | — |
| Ultralytics | 8.4.191 | PyPI | — | AGPL-3.0 | — |
| Pesos YOLO11s-seg (COCO) | 8.4.191 | Descarga automática de Ultralytics | SHA-256 `1caa81c0195412efa411b632bcfb8c184939dddb6ae41f6a80c41b211ff257c3` | — | AGPL-3.0, como el paquete |
| rfdetr | 1.11.2 | PyPI | — | Apache-2.0 | — |
| Pesos RF-DETR Seg Nano (COCO) | `rf-detr-seg-n-ft.pth` | storage.googleapis.com/rfdetr | MD5 `9995497791d0ff1664a1d9ddee9cfd20` (coincide con el publicado); SHA-256 `a44613a4ecd6b5ba61a62002c600b0b6cb7a9da2936a45317ec4b62c635fb99b` | — | Apache-2.0 (README de rf-detr: todos los tamaños Seg) |
| Pesos RF-DETR Seg Small (COCO) | `rf-detr-seg-s-ft.pth` | storage.googleapis.com/rfdetr | MD5 `0a2a3006381d0c42853907e700eadd08` (coincide); SHA-256 `6de3da31b2572cac214a1c76cce4a92a13966d56390ac2b3a3de9a8dc2b2bca3` | — | Apache-2.0 |
| ONNX Runtime | 1.31.1 | PyPI | — | MIT | — |
| IOP-Compass | final_1000 (descarga del 2026-11-11, zip de 44,2 GB) | ditto.ing.unimore.it/iop-compass (con cuenta) | Huella de las 5000 anotaciones: SHA-256 `02f7fccac31095ee6816cafe75664a61d8bd61af90dfc46d0aa374e12d80ca1d`, calculada por `annotations_fingerprint()` en `research/audit_iop.py`: SHA-256 de, para cada JSON en orden de ruta relativa POSIX, la ruta en UTF-8 + byte 0x00 + SHA-256 del contenido | El repositorio no publica licencia de código: solo se leyó | CC BY-NC-SA 4.0 (página del proyecto). El desarrollador aceptó términos al crear la cuenta: revisarlos antes de copiar el dataset a la nube |
| COde | zip de Hugging Face | huggingface.co/datasets/zirak-ai/COde (doi:10.57967/hf/6421) | SHA-256 `f4e5664ef4d57caa7ecdf68963551dccf0053e380efeb2f198f1cd5d2d68781d` | — | CC BY 4.0 + acuerdo de uso: no reidentificar, uso legítimo y manejo seguro |

**Consecuencia de las licencias.** YOLO11 (AGPL-3.0) e IOP-Compass (no comercial) quedan para la línea de tesis. Una versión para clínicas (ODON-275) tendría que partir de RF-DETR (Apache-2.0) y de datos con licencia comercial, o comprar una licencia de Ultralytics.

## 7. Decisión

**Continuar con el plan de ODON-13 sin cambios de fondo**, con estos ajustes:

1. **Modelos:** YOLO11s-seg como principal y **RF-DETR Seg Small** como comparador en la misma partición por paciente y con los mismos archivos (RF-DETR lee el formato YOLO-seg). En CPU, Small no supone un costo: su p95 es de 0,78 s con 2 núcleos en ONNX.
2. **Inferencia en CPU:** viable. El peor p95 es de 1,11 s por foto, frente a un umbral de 10 s fijado antes de medir, en una laptop con batería y limitada a 2 y 4 núcleos. Falta confirmarlo en el equipo de la clínica.
3. **Datos:** IOP-Compass confirma contornos por pieza con FDI en 1000 pacientes × 5 vistas. Los terceros molares son la clase débil: se reportan aparte y se tratan como caso de «no visible» poco fiable.
4. **Entrenamiento:** sin volteo horizontal en ambos modelos. YOLO en local y la tanda pesada (RF-DETR completo y curva de aprendizaje) en la nube, solo con datos públicos (comentario en ODON-267).
5. **Riesgo abierto:** el equipo real de la clínica (CPU y RAM) sigue sin medirse.
