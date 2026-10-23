# OdontoNet — AI Service

Este directorio está reservado para el futuro microservicio de inteligencia artificial de OdontoNet.

## Objetivo

Desarrollar un servicio independiente para procesar imágenes odontológicas y asistir en la generación de periodontogramas.

## Estado

**No implementado.**

El desarrollo del modelo de IA se realizará independientemente del sistema clínico.

## Integración prevista

El backend de OdontoNet se comunicará con el servicio mediante una API.

Las mediciones generadas por inteligencia artificial deberán ser revisadas y validadas por un profesional odontológico antes de incorporarse al expediente clínico.

## Consideraciones

- Mantener dependencias independientes del backend clínico.
- No incluir imágenes de pacientes ni datasets privados en Git.
- Versionar los contratos de comunicación entre servicios.
- Documentar modelos, métricas y limitaciones antes de su integración.
