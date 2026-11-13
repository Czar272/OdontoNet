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

Sin corrida de RF-DETR evaluada: la comparación es trabajo futuro (decisión del 2026-11-12).
