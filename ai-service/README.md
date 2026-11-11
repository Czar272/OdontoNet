# OdontoNet — AI Service

Este directorio está reservado para el futuro microservicio de inteligencia artificial de OdontoNet.

## Objetivo

Desarrollar un servicio independiente para procesar imágenes odontológicas y asistir en la generación de periodontogramas.

## Estado

**No implementado.** El contrato v1 está definido en [`docs/AI_INTEGRATION.md`](../docs/AI_INTEGRATION.md) (ODON-250); la implementación es ODON-269.

El desarrollo del modelo de IA se realizará independientemente del sistema clínico.

## Integración prevista

El backend de OdontoNet llama a este servicio por HTTP en la red interna (`GET /health`, `GET /v1/model`, `POST /v1/analyses/tooth-status`). El servicio corre en CPU, sin internet, no recibe identificadores de paciente ni de clínica y no guarda imágenes. La primera versión sugiere presencia o ausencia de cada pieza FDI.

Las mediciones generadas por inteligencia artificial deberán ser revisadas y validadas por un profesional odontológico antes de incorporarse al expediente clínico.

## Consideraciones

- Mantener dependencias independientes del backend clínico.
- No incluir imágenes de pacientes ni datasets privados en Git.
- Versionar los contratos de comunicación entre servicios.
- Documentar modelos, métricas y limitaciones antes de su integración.
