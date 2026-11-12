## Criterio de aceptación (§7.3)

Modelo `yolo11s-seg-f100-s0`, prueba, piezas 11–47 sin terceros molares, umbral 0,927 (elegido en validación).

| Métrica | Valor | IC 95 % | Exigido |
| --- | --- | --- | --- |
| Sensibilidad de «no visible» | 0,90 | 0,80–1,00 | ≥ 0,80 |
| Especificidad | 0,96 | 0,95–0,97 | ≥ 0,95 |

**Resultado: cumple** (TP 27, FN 3, TN 2668, FP 102).

## Curva de aprendizaje de YOLO11s-seg (30 épocas por corrida; prueba, media ± DE entre semillas)

| % de pacientes | Semillas | mAP50 de máscara | Numeración | Sensibilidad «no visible» | Especificidad |
| --- | --- | --- | --- | --- | --- |
| 25 | 1 | 0,89 ± — | 0,98 ± — | 0,80 ± — | 0,96 ± — |
| 50 | 1 | 0,91 ± — | 0,98 ± — | 0,90 ± — | 0,95 ± — |
| 100 | 1 | 0,92 ± — | 0,99 ± — | 0,87 ± — | 0,95 ± — |

## YOLO11s-seg frente a RF-DETR Seg Small (100 %, prueba)

| Modelo | Semillas | mAP50 de máscara | Sensibilidad «no visible» | Especificidad |
| --- | --- | --- | --- | --- |
| yolo11s-seg | 1 | 0,92 ± — | 0,90 ± — | 0,96 ± — |
| rfdetr-seg-small | 0 | — ± — | — ± — | — ± — |
