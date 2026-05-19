# 🦷 OdontoNet

> Sistema inteligente de gestión odontológica con automatización clínica asistida por inteligencia artificial.

---

## Descripción

**OdontoNet** es una plataforma de gestión clínica odontológica diseñada para optimizar y modernizar los procesos clínicos y administrativos dentro de consultorios dentales. El sistema integra herramientas de administración de pacientes, historiales clínicos, almacenamiento de imágenes odontológicas y generación de periodontogramas, incorporando además módulos de inteligencia artificial para automatizar procesos de análisis periodontal.

El objetivo principal del proyecto es desarrollar una solución escalable y multiplataforma que permita mejorar la eficiencia clínica, reducir tiempos de evaluación y facilitar el trabajo de los profesionales de odontología mediante herramientas digitales modernas.

Uno de los componentes más importantes de OdontoNet es la implementación de un modelo de visión por computadora capaz de analizar imágenes intraorales obtenidas desde dispositivos móviles para asistir en la generación automática de periodontogramas y futuras funcionalidades de diagnóstico asistido.

---

# Objetivos del Proyecto

## Objetivo General

Desarrollar un sistema inteligente de gestión odontológica que integre herramientas clínicas, administrativas y modelos de inteligencia artificial para automatizar procesos periodontales y mejorar la eficiencia operativa en clínicas dentales.

---

## Objetivos Específicos

- Gestionar pacientes, historiales clínicos y registros odontológicos.
- Permitir el almacenamiento y administración de imágenes clínicas.
- Implementar un módulo digital de periodontograma.
- Desarrollar un sistema de inteligencia artificial para automatizar mediciones periodontales mediante visión por computadora.
- Facilitar futuras integraciones con aplicaciones móviles y de escritorio.
- Diseñar una arquitectura escalable basada en microservicios.

---

# Características Principales

- Gestión de pacientes
- Historial clínico odontológico
- Gestión de imágenes clínicas
- Periodontograma digital
- Sistema de autenticación y roles
- Dashboard administrativo
- Integración con inteligencia artificial
- Arquitectura modular y escalable
- API REST
- Compatibilidad multiplataforma

---

# Arquitectura General

OdontoNet estará dividido en dos componentes principales:

---

## Sistema Clínico

Encargado de:

- Gestión administrativa
- Pacientes
- Usuarios
- Imágenes clínicas
- Historiales
- Periodontogramas

### Tecnologías previstas

- React
- TypeScript
- TailwindCSS
- FastAPI
- PostgreSQL

---

## Microservicio de Inteligencia Artificial

Encargado de:

- Procesamiento de imágenes
- Detección periodontal
- Análisis mediante redes neuronales
- Automatización de mediciones clínicas

### Tecnologías previstas

- Python
- PyTorch
- OpenCV
- FastAPI

---

# Arquitectura de Comunicación

```txt
Frontend React
       │
       ▼
Backend FastAPI
       │
       ▼
Microservicio IA
