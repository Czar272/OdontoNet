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
| 25 | 2 | 0,89 ± 0,00 | 0,98 ± 0,00 | 0,80 ± 0,00 | 0,96 ± 0,00 |
| 50 | 2 | 0,91 ± 0,00 | 0,98 ± 0,00 | 0,90 ± 0,00 | 0,95 ± 0,00 |
| 100 | 2 | 0,93 ± 0,00 | 0,98 ± 0,01 | 0,83 ± 0,05 | 0,97 ± 0,02 |

## Anexo exploratorio: RF-DETR Seg Small frente a YOLO11s-seg (100 %, prueba)

Añadido después de pasar la comparación planeada a trabajo futuro: 1 semilla y épocas distintas; descriptivo, sin afirmar cuál modelo es mejor.

| Modelo | Épocas | mAP50 de máscara | Sensibilidad «no visible» (IC 95 %) | Especificidad (IC 95 %) | Especificidad terceros molares |
| --- | --- | --- | --- | --- | --- |
| `yolo11s-seg-f100-s0-e30` | 30 | 0,92 | 0,87 (0,74–1,00) | 0,953 (0,94–0,97) | 0,50 |
| `rfdetr-seg-small-f100-s0-e10` | 10 | 0,94 | 0,93 (0,83–1,00) | 0,955 (0,94–0,97) | 0,39 |

Semilla 0, RF-DETR − YOLO (pareado por paciente): sensibilidad 0,067 (IC 95 % 0,00–0,19), especificidad 0,001 (IC 95 % -0,01–0,01), mAP50 0,019.
