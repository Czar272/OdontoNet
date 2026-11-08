# Privacidad y protección de datos (borrador)

> **Estado: borrador técnico para revisión (ODON-218).** Describe qué datos guarda OdontoNet, quién accede, qué controles están implementados y qué falta decidir. **No es un dictamen legal**: debe revisarlo un abogado con experiencia en protección de datos, y el uso de datos de pacientes para investigación debe pasar por el comité de ética que corresponda. Hasta entonces el sistema no se usa con datos reales.

## 1. Contexto normativo (por verificar con un abogado)

Lo que sigue proviene de una búsqueda del 2026-11-07. Nada de esto está verificado legalmente:
- **Ley de protección de datos:** no se encontró una ley general de protección de datos personales vigente en Guatemala. La iniciativa 6464 seguía en estudio en comisión en julio de 2026.
- **Ley de ciberseguridad:** el Decreto 26-2026 (Ley Marco de Ciberseguridad) se aprobó el 3 de noviembre de 2026 y entra en vigor 30 días después de su publicación. Según la nota de prensa consultada, obliga sobre todo a las instituciones públicas.
- **Expediente clínico:** no se encontró un plazo legal de conservación.

El sistema se diseñó con criterios de protección prudentes (mínimo acceso, auditoría, cifrado de respaldos), sin depender de una obligación legal concreta.

## 2. Inventario de datos

| Dato | Tabla(s) | Para qué | Quién accede | Notas |
| --- | --- | --- | --- | --- |
| Identificación y contacto del paciente: nombre, fecha de nacimiento, teléfono, correo, dirección, doctor asignado, fecha de alta | `patients` | Atención, agenda, contacto | Administración, doctores y recepción de la misma clínica | Recepción necesita el contacto para confirmar citas |
| Citas: fecha, duración, estado, motivo breve | `appointments`, `appointment_status_changes` | Agenda | Los tres roles | El motivo de la cita no debe contener datos clínicos |
| Historia médica: condiciones, alergias, medicación, tabaco, alcohol, hábitos de higiene, motivo de consulta | `patient_medical_histories` (versionada) | Atención clínica segura | Administración y doctores editan; recepción solo consulta (decisión ODON-150) | **Dato de salud.** Revisar si recepción necesita verla (sección 6) |
| Consultas clínicas: motivo, hallazgos, diagnóstico, procedimientos, indicaciones | `clinical_visits`, `clinical_visit_revisions` | Expediente | Administración y doctores | Dato de salud. Las correcciones quedan en revisiones; nada se borra |
| Plan de tratamiento | `treatments`, `treatment_status_changes` | Expediente | Administración y doctores | Dato de salud |
| Periodontograma: mediciones por pieza y sitio, notas | `periodontal_exams`, `_teeth`, `_sites`, `_revisions` | Expediente; base para la investigación con IA | Administración y doctores | Dato de salud |
| Fotografías intraorales y sus metadatos | `patient_images`, `patient_image_revisions`, carpeta privada `IMAGE_STORAGE_DIR` | Expediente; posible investigación | Administración y doctores | Dato de salud. Recodificadas sin metadatos EXIF |
| Consentimiento para fotografías y uso en investigación (`research_use`) | `patient_photo_consents` (versionado) | Base para tomar y usar fotos | Administración y doctores | Sin consentimiento vigente no se pueden subir fotos |
| Accesos al original de una imagen | `image_access_logs` | Trazabilidad | Administración | Solo ids y fecha |
| Usuarios del personal: nombre, correo, rol, contraseña (hash bcrypt) | `users` | Acceso al sistema | Administración | La contraseña nunca se guarda ni se devuelve en claro |
| Enlaces de recuperación de contraseña | `password_reset_tokens` | Recuperar acceso | Nadie (solo el sistema) | Solo el hash del enlace; caducan |
| Intentos de autenticación | `auth_attempts` | Limitar ataques de fuerza bruta | Nadie (solo el sistema) | Hash del correo e IP; se depuran a diario |
| Auditoría de cambios y exportaciones | `audit_events` | Saber quién cambió qué | Administración (toda la clínica) y cada doctor (lo suyo) | Solo ids y nombres de campo, sin valores |
| Respaldos | Repositorios restic (local y nube) | Recuperación ante fallas | Custodios de la clave de cifrado | Cifrados antes de salir del servidor |

**Datos que el sistema no guarda:** documentos de identidad, datos de pago, datos de terceros (familiares) ni la ubicación del dispositivo.

## 3. Acceso mínimo (implementado)

- **Aislamiento por clínica:** cada consulta se limita a la clínica del usuario autenticado, y un recurso de otra clínica responde 404. Las claves foráneas compuestas impiden mezclar datos de clínicas.
- **Roles:** administración, doctor y recepción, según la matriz de `PERMISSIONS.md`, aplicada en el servidor y reflejada en la interfaz. Recepción no accede a consultas, tratamientos, imágenes ni periodontograma.
- **Sesión:**
  - token JWT de duración limitada;
  - cambiar la contraseña cierra las demás sesiones;
  - límite de intentos de inicio de sesión;
  - contraseñas de al menos 10 caracteres y no comunes.
- **Fotografías:** almacenamiento privado, nunca servido como archivo estático, con `Cache-Control: no-store`. Se registra cada apertura del original.
- **Respuestas de la API:** `Cache-Control: no-store` y cabeceras de seguridad.
- **Registros:** solo ids, nunca datos personales ni contraseñas.

## 4. Consentimiento y origen de las imágenes (implementado)

- Para subir fotos hace falta un consentimiento vigente y versionado (`granted`), con fecha de firma y quien lo registró.
- El uso en investigación es una autorización **separada** (`research_use`); no se deduce del consentimiento clínico.
- Cada imagen registra su origen (cámara intraoral, teléfono, cámara, externa), la vista y la fecha de toma.
- **Pendiente** (decisión del comité de ética): el texto del consentimiento que firma el paciente, cómo se revoca el uso en investigación y qué pasa con imágenes ya usadas en un conjunto de datos.

## 5. Retención (propuesta, pendiente de criterio legal)

| Dato | Propuesta | Motivo |
| --- | --- | --- |
| Expediente clínico (historia, consultas, tratamientos, periodontogramas, imágenes) | Conservar sin borrar mientras no haya un plazo legal; los registros se archivan o anulan, nunca se borran | No se encontró un plazo legal en Guatemala; borrar un expediente es irreversible |
| Auditoría | Al menos lo mismo que el expediente al que se refiere | Sin ella no se puede reconstruir quién cambió un expediente (decisión ODON-222) |
| Respaldos | 7 diarios, 4 semanales, 12 mensuales y uno por año | Ver `BACKUPS.md`. Los anuales se conservan hasta que exista un plazo legal |
| Intentos de autenticación | 1 día | Dato operativo; solo sirve para el límite de intentos |
| Enlaces de recuperación | Hasta que caducan o se usan | Dato operativo |
| Usuarios dados de baja | Se desactivan, no se borran | La auditoría y el expediente los referencian |

Cuando exista un plazo, la depuración necesitará un procedimiento propio (con respaldo previo y su propia auditoría), que hoy no existe.

## 6. Preguntas para la revisión

**Para el abogado:**
1. ¿Qué normas aplican hoy a una clínica dental privada en Guatemala respecto a los datos de salud de sus pacientes? ¿Existe un plazo de conservación del expediente clínico?
2. ¿Exige algo el Decreto 26-2026 (Ley Marco de Ciberseguridad) a una clínica privada o a quien le provee software?
3. ¿Se pueden guardar respaldos cifrados en un proveedor de nube fuera del país (por ejemplo, en EE. UU.)? ¿Hace falta informarlo al paciente o pedirle consentimiento?
4. ¿Qué derechos tiene el paciente sobre sus datos (acceso, corrección, copia) y en qué plazo hay que atenderlos?
5. ¿Qué hacer ante una filtración: a quién avisar y en qué plazo?

**Para el comité de ética:**
6. ¿El formulario de consentimiento separado para investigación (`research_use`) es suficiente? ¿Qué debe decir?
7. ¿Cómo deben seudonimizarse las imágenes y los datos clínicos para el entrenamiento y la evaluación del modelo de IA, y quién custodia la tabla de correspondencia?
8. ¿Qué pasa si un paciente revoca el uso en investigación después de que su imagen entró en un conjunto de datos?

**Para la clínica:**
9. ¿Recepción necesita consultar la historia médica (hoy puede verla, no editarla), o basta con alertas como las alergias?
10. ¿Quiénes serán los dos custodios de la clave de cifrado de los respaldos?

## 7. Fuera de alcance de este documento

- La seudonimización para el conjunto de datos de investigación (épica de IA, ODON-13).
- HTTPS y el endurecimiento del servidor del despliegue (épica ODON-12).
