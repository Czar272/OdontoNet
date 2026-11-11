# Prueba de aceptación del MVP (UAT)

> ODON-246. Este documento define la prueba (ODON-247). La ejecución es ODON-248 y el registro de hallazgos y la aprobación, ODON-249. Se imprime o se copia por cada sesión: las columnas de resultado se llenan a mano.

## 1. Objetivo y criterio de aprobación

Comprobar con el personal de la clínica que OdontoNet permite trabajar un día normal de punta a punta antes de usarlo con pacientes reales. **No** es una prueba de seguridad ni de rendimiento: el aislamiento entre clínicas, los permisos por rol y los casos límite ya los cubren las pruebas automáticas (`PROJECT_STATUS.md`, «Estado verificado»).

El MVP queda **aceptado** cuando se cumplen las tres condiciones:

1. Todos los escenarios marcados **[C]** (críticos) dan «OK».
2. No queda abierto ningún defecto **crítico** (§5).
3. El responsable de la clínica firma el acta (§7) y acepta el alcance (§2). Los defectos mayores abiertos deben tener un plan acordado en el acta.

Si un escenario crítico falla, se corrige el defecto, se repite **ese** escenario y los que dependan de él, y se anota en el acta.

## 2. Alcance

**Incluido:**
- Inicio de sesión y sesión.
- Usuarios, doctores y sus horarios.
- Pacientes, agenda y citas.
- Historia médica, consultas y tratamientos.
- Consentimiento y fotografías clínicas.
- Periodontograma manual: captura, guardado, PDF y comparación.
- Historial, inicio, reportes y Auditoría.
- Instalación en el equipo de la clínica y respaldos.

**Fuera de alcance:**
- La IA periodontal (épica ODON-13, posterior al MVP).
- El alta de clínicas nuevas por `superadmin`.
- Las ausencias de doctores (ODON-258).
- La versión para móvil.
- La importación de datos de otro sistema.

## 3. Condiciones

- **Solo datos ficticios.** Hasta que exista el dictamen de ética y la revisión legal (ODON-218/220), no se registra ningún paciente real.
  - Nombres inventados y teléfonos `5555-0001`, `5555-0002`…
  - Correos `@ejemplo.com`.
  - Las fotografías son de un modelo dental (tipodonto) o imágenes sin personas, **nunca** de un paciente.
- **Instalación de prueba:** en el equipo que será el servidor, siguiendo `DEPLOYMENT.md`, con una clínica de nombre ficticio («Clínica Prueba UAT»). La instalación definitiva se hace limpia después de la aceptación, para que los datos ficticios no se mezclen con los reales.
- **Equipos:** el servidor y al menos un segundo equipo de la clínica conectado por la red, como lo usará el personal.
- **Participantes:** el responsable de la clínica (odontólogo, con rol de administración), una persona de recepción y, si es posible, un segundo doctor. El desarrollador conduce la sesión y anota, sin operar el sistema por ellos.
- **Duración estimada:** dos sesiones de 2 horas: preparación y recepción en la primera, y la parte clínica y administración en la segunda. La fila O3 de §4 se revisa al día siguiente.
- **Material:** el manual por rol (`docs/manual/`) impreso o en PDF. Los participantes lo usan en lugar de recibir instrucciones verbales; si un paso del manual no se entiende, se anota como hallazgo.

## 4. Escenarios

Las columnas de resultado son: **R** = OK / Falla / Bloqueado; **Obs.** = observaciones, tiempo o hallazgo (con su número de §6). **[C]** marca un escenario crítico.

### Preparación (desarrollador, con el responsable presente)

| Id | Escenario | Resultado esperado | R | Obs. |
| --- | --- | --- | --- | --- |
| P1 [C] | Instalar con `deploy.ps1 -FirstInstall` y crear la clínica con `bootstrap_clinic` (`DEPLOYMENT.md`, «Instalar»). | `https://odontonet.internal/api/health` responde correctamente y el administrador inicia sesión. | | |
| P2 [C] | Conectar un segundo equipo: nombre y certificado («Conectar cada equipo»). | El navegador abre OdontoNet sin advertencia de certificado. | | |
| P3 | Iniciar sesión desde el segundo equipo y revisar `remote_ip` en los logs del proxy. | Aparece la IP del equipo; si aparece una IP interna de Docker, se aplica el ajuste de `DEPLOYMENT.md` y se anota. | | |
| P4 [C] | Configurar los respaldos, ejecutar uno y luego el ensayo `restore-check.ps1` (`BACKUPS.md`). | El respaldo termina y el ensayo de restauración pasa. | | |

### Acceso y personal (administración)

| Id | Escenario | Resultado esperado | R | Obs. |
| --- | --- | --- | --- | --- |
| A1 [C] | Crear un usuario de recepción y uno de doctor, y el perfil y horario semanal del doctor. | Ambos pueden iniciar sesión; el doctor aparece en Agenda con su horario. | | |
| A2 [C] | Iniciar sesión con cada rol y revisar el menú. | Cada rol ve solo lo indicado en el manual («Conocer la pantalla»). | | |
| A3 | Iniciar sesión sin «Recuérdame», cerrar el navegador y volver a abrirlo. | Pide iniciar sesión otra vez. | | |
| A4 | Cambiar la contraseña propia. Luego, desde administración, asignar una contraseña nueva a otro usuario. | Ambas contraseñas nuevas funcionan; la anterior ya no. | | |
| A5 [C] | Desactivar el usuario de prueba de doctor y tratar de entrar con él. Luego reactivarlo. | Desactivado no entra; reactivado sí. | | |

### Recepción

| Id | Escenario | Resultado esperado | R | Obs. |
| --- | --- | --- | --- | --- |
| R1 [C] | Registrar tres pacientes ficticios y buscar uno por nombre, otro por teléfono y otro por apellido. | Se encuentran; los datos guardados coinciden con lo escrito. | | |
| R2 [C] | Agendar una cita para mañana con el doctor de prueba. | Aparece en el calendario con el color del doctor. | | |
| R3 [C] | Agendar otra cita del mismo doctor a la misma hora. | El sistema avisa del cruce e indica con quién; no la guarda. | | |
| R4 | Agendar fuera del horario del doctor. | Avisa y muestra el horario; «Agendar de todas formas» la guarda. | | |
| R5 | Reprogramar una cita arrastrándola en el calendario y otra desde el detalle. | Ambas quedan en el horario nuevo; el historial de la cita lo registra. | | |
| R6 [C] | Confirmar una cita desde «Por confirmar» y cancelar otra con motivo. | Cambian de estado; la cancelada libera el horario. | | |
| R7 [C] | Abrir la ficha de un paciente con el usuario de recepción. | Ve datos generales e historia médica en lectura; no ve consultas, imágenes ni periodontograma. | | |
| R8 | Archivar un paciente y reactivarlo. | Archivado no admite citas nuevas; reactivado sí. | | |

### Atención clínica (doctor)

| Id | Escenario | Resultado esperado | R | Obs. |
| --- | --- | --- | --- | --- |
| D1 [C] | Llenar la historia médica de un paciente y luego modificarla. | Se guarda; la versión anterior queda en el historial con autor y fecha. | | |
| D2 [C] | Registrar una consulta (motivo, hallazgos, diagnóstico, procedimientos) y editarla. | Se guarda; la edición queda registrada como revisión. | | |
| D3 | Registrar un tratamiento en una pieza desde el odontograma y avanzarlo de estado. | Cambia de estado según el manual; queda en el historial. | | |
| D4 [C] | Registrar el consentimiento de fotografías y subir dos fotos (de tipodonto) con origen y vista. | Se suben; la galería las muestra con miniatura. Sin consentimiento, la subida no está disponible. | | |
| D5 | Anular una foto con motivo y revisar «Accesos» de la otra. | La anulada sigue visible como anulada; Accesos muestra quién abrió el original. | | |
| D6 [C] | Crear un periodontograma, capturar con el teclado los sondajes y márgenes de una arcada, marcar una pieza ausente y otra con sangrado. | El dibujo y el resumen se actualizan al escribir; aparece «Todo guardado». | | |
| D7 | Usar «Llenar con valores de salud» en las piezas restantes y luego «Deshacer». | Los valores aparecen en gris cursiva y «Deshacer» los quita. | | |
| D8 [C] | Desconectar la red del equipo mientras se edita, escribir dos valores, reconectar y reabrir el examen. | Ofrece «Recuperar cambios» y los recupera. | | |
| D9 | Abrir el mismo borrador como administración en otro equipo, cambiar un valor y luego guardar desde el primero. | El primero recibe el aviso de que hay una versión más reciente y puede cargarla; no se pierde nada en silencio. | | |
| D10 [C] | Finalizar el examen y exportar el PDF. | Queda finalizado y no editable; el PDF muestra la grilla, el dibujo y el aviso de que no es un diagnóstico. | | |
| D11 | Registrar un segundo examen a partir del anterior, finalizarlo y usar «Comparar». | Muestra las diferencias de resumen y por sitio. | | |
| D12 | Revisar la pestaña de historial del paciente. | Muestra consultas, tratamientos, imágenes y periodontogramas en orden cronológico. | | |

### Administración e inicio

| Id | Escenario | Resultado esperado | R | Obs. |
| --- | --- | --- | --- | --- |
| M1 | Revisar Inicio con cada rol. | Muestra la agenda de hoy y los indicadores sin datos del expediente. | | |
| M2 | Generar un reporte de citas por semana y exportar el CSV (administración). | Las cifras coinciden con las citas creadas en la sesión; el CSV abre en Excel. | | |
| M3 [C] | Abrir Auditoría y filtrar por el usuario de doctor. | Aparecen sus cambios de la sesión, solo con nombres de campos, sin valores. | | |
| M4 | Editar los datos de la clínica (teléfono, dirección). | Se guardan y los ven los demás roles. | | |

### Operación

| Id | Escenario | Resultado esperado | R | Obs. |
| --- | --- | --- | --- | --- |
| O1 [C] | Reiniciar el servidor y esperar a que arranque Windows. | OdontoNet vuelve a estar disponible sin intervención y los datos de la sesión siguen ahí. | | |
| O2 | Cerrar sesión en un equipo e intentar volver con el botón «Atrás» del navegador. | No muestra datos sin iniciar sesión de nuevo. | | |
| O3 [C] | Al día siguiente, comprobar que el respaldo programado se ejecutó (registro en `%LOCALAPPDATA%\OdontoNet\backup-logs`). | Hay un respaldo nuevo sin errores. | | |

### Opinión de los participantes (al final de cada sesión)

1. ¿Qué tarea le costó más y por qué?
2. ¿Qué falta para usarlo en un día real de la clínica?
3. ¿Qué haría distinto a como trabaja hoy (papel u otro sistema)?
4. ¿Algún texto, nombre o término clínico que esté mal o confunda?

## 5. Gravedad de los defectos

| Gravedad | Definición | Efecto en la aceptación |
| --- | --- | --- |
| **Crítico** | Se pierde o se expone información; un dato clínico se guarda distinto de lo escrito; un rol ve lo que no debe; o una tarea principal no se puede completar de ninguna forma. | Bloquea la aceptación. |
| **Mayor** | Una tarea principal se completa solo con un rodeo o con ayuda del desarrollador. | Requiere un plan con fecha en el acta. |
| **Menor** | Error de texto, de presentación o de una función secundaria, con alternativa sencilla. | Se registra como historia en Jira. |
| **Sugerencia** | Mejora o cambio de flujo que pide el usuario. | Se registra para priorizar después. |

## 6. Registro de hallazgos

Cada hallazgo se convierte en un ticket de Jira (ODON-249) que referencia su número.

| N.º | Escenario | Gravedad | Descripción (qué se hizo, qué pasó, qué se esperaba) | Ticket |
| --- | --- | --- | --- | --- |
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

## 7. Acta de aceptación

| Campo | Valor |
| --- | --- |
| Clínica | |
| Fechas de las sesiones | |
| Versión probada (commit) | |
| Escenarios críticos OK / total | |
| Defectos críticos abiertos | |
| Defectos mayores abiertos y plan | |
| Decisión | Aceptado / Aceptado con condiciones / No aceptado |

| Rol | Nombre | Firma | Fecha |
| --- | --- | --- | --- |
| Responsable de la clínica | | | |
| Desarrollador | | | |

La aceptación cubre el alcance de §2 con datos ficticios. El uso con pacientes reales queda sujeto, además, al dictamen de ética y la revisión legal (ODON-218/220) y a los respaldos programados en el servidor (`BACKUPS.md`).
