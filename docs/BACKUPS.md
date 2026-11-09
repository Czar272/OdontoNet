# Respaldos y restauración

Procedimiento de respaldo de OdontoNet (ODON-226). Aplica al servidor de la clínica; en desarrollo sirve para ensayarlo con datos sintéticos.

## Qué se respalda y cómo

Cada respaldo incluye juntos:
- **la base de datos**: volcado `pg_dump` en formato custom;
- **su manifiesto**: versión de Alembic, filas por tabla y final de la cadena de auditoría de cada clínica, sin datos de pacientes. El volcado y el manifiesto salen del mismo snapshot de la base (`pg_export_snapshot` + `pg_dump --snapshot`), así que lo que pase en la API durante el respaldo no produce diferencias en el ensayo;
- **la carpeta de imágenes clínicas** (`IMAGE_STORAGE_DIR`).

La base se respalda primero. Las imágenes son inmutables, así que todo archivo registrado en la base ya existe en la carpeta; una subida durante el respaldo solo deja un archivo sin registro, que `verify_images` informa como huérfano.

El cifrado lo hace [restic](https://restic.net) en el servidor, antes de que los datos salgan (AES-256 con Poly1305 según su documentación de diseño; por verificar en restic.readthedocs.io). El proveedor de la nube solo guarda bloques cifrados: no puede ver los datos ni saber de quién son. El volcado sin cifrar solo existe en una carpeta temporal del servidor y, un momento, en `/tmp` del contenedor; los scripts borran ambos aunque fallen. Si el proceso se interrumpe a la fuerza (apagado, límite de 3 h de la tarea), el siguiente respaldo o ensayo los limpia al empezar.

## Esquema: 3-2-1 más una copia que no se puede borrar desde el servidor

| Copia | Dónde | Para qué |
| --- | --- | --- |
| 1 | La base y la carpeta en uso, en el servidor de la clínica | Trabajo diario; la aplicación funciona sin internet |
| 2 | Repositorio restic local, en un disco externo o NAS (otro dispositivo) | Recuperación rápida ante fallas o errores |
| 3 | Repositorio restic en la nube, fuera de la clínica (Backblaze B2) | Incendio, robo o daño del local; ransomware |

Se basa en la guía #StopRansomware de CISA (respaldos fuera de línea, cifrados y con pruebas periódicas de restauración; https://www.cisa.gov/stopransomware/ransomware-guide) y en el NCSC del Reino Unido (3-2-1, una copia que un incidente no pueda alcanzar, credenciales de nube limitadas; https://www.ncsc.gov.uk/blog-post/offline-backups-in-an-online-world). Ambas fuentes están por verificar antes de citarlas formalmente.

**Nube: qué está probado y qué no.** El diseño usa en el servidor una clave de aplicación de B2 sin permiso de borrado (`deleteFiles`) y un bucket que conserva las versiones anteriores, para que el servidor solo agregue respaldos. **Esto no se ha ensayado todavía** (solo se ensayó el repositorio local). Con la API compatible con S3, un borrado sin versión puede «ocultar» un archivo (marcador de borrado) en lugar de borrarlo; las versiones siguen en el bucket, pero restic deja de verlas. Pendiente antes de usar la nube con datos reales: (1) probar un borrado con la clave restringida, (2) documentar cómo recuperar versiones ocultas (desde la consola de B2 o quitando los marcadores), y (3) evaluar Object Lock de B2 como alternativa. La depuración de la nube se hace aparte, desde otro equipo, con una clave con borrado que no vive en el servidor.

## Frecuencia y retención

Ninguna fuente oficial fija números, así que se usa una práctica estándar, declarada como decisión de diseño:
- **Diario**, por la noche: lo máximo que se pierde ante una falla es un día de trabajo.
- **Antes de cada migración**: `backup.ps1 -Tag pre-migracion`.
- **Retención del repositorio local:** 7 diarios, 4 semanales, 12 mensuales y uno por año. Los anuales no se borran mientras no exista un plazo legal (ODON-218).
- **Retención en la nube:** se depura una vez al mes desde otro equipo, con una clave de administración (con borrado) que no se guarda en el servidor: `restic -r <repo-nube> --password-file <archivo> forget --host odontonet --tag odontonet --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --keep-yearly 1000 --prune`. Si queda un bloqueo de una ejecución interrumpida: `restic -r <repo> unlock`.
- **Ensayo de restauración automático** cada 4 semanas, 2 horas después del respaldo para no usar el repositorio a la vez (además, restic espera si el repositorio está ocupado), más un ensayo manual documentado (abajo).

## Puesta en marcha (una sola vez)

1. Instala restic: `winget install restic.restic`.
2. Crea la contraseña de cifrado, en una sola línea, en un archivo fuera del repositorio (por ejemplo `%USERPROFILE%\.odontonet\restic-password.txt`). Para generarla: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
3. **Custodia de la contraseña**:
   - guárdala también en un gestor de contraseñas y en papel sellado, con dos custodios en la clínica;
   - sin ella no hay forma de restaurar;
   - si se pierde, los respaldos no sirven.
4. Copia `scripts\backup\backup.env.example` a `%USERPROFILE%\.odontonet\backup.env` y completa las rutas. Nunca lo subas al repositorio. Contiene la clave de la nube en texto plano: restringe sus permisos a la cuenta que corre los respaldos (`icacls backup.env /inheritance:r /grant:r "%USERNAME%:F"`).
5. **Nube (opcional), Backblaze B2**:
   - crea un bucket **privado**, con la configuración de ciclo de vida «conservar todas las versiones»;
   - crea una clave de aplicación limitada a ese bucket con `listBuckets`, `listFiles`, `readFiles` y `writeFiles`, **sin `deleteFiles`**;
   - pon el endpoint S3 en `ODONTONET_BACKUP_CLOUD_REPO` y la clave en `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.

   Los primeros 10 GB son gratuitos y luego unos 6,95 USD por TB al mes, según comparativas de 2026 (por verificar en https://www.backblaze.com/cloud-storage/pricing). Se puede cambiar a otro servicio compatible con S3 sin tocar los scripts.
6. Primer respaldo, que inicializa los repositorios: `powershell -ExecutionPolicy Bypass -File scripts\backup\backup.ps1 -Config $env:USERPROFILE\.odontonet\backup.env -Init`.
7. Programa las tareas: `powershell -ExecutionPolicy Bypass -File scripts\backup\register-tasks.ps1 -Config $env:USERPROFILE\.odontonet\backup.env -At 21:00`. Corren solo con la sesión del usuario iniciada (Docker Desktop vive en su sesión); si el equipo está apagado a esa hora, corren al encenderlo.
8. **Revisa los resultados**: cada ejecución deja un registro en `%LOCALAPPDATA%\OdontoNet\backup-logs` (se guardan los últimos 60), y el Programador de tareas muestra el «Último resultado» (0 = correcto). Un respaldo o ensayo fallido no avisa solo: revísalo al menos una vez por semana.

## Restaurar

**Ensayo, sin tocar nada en uso:** `scripts\backup\restore-check.ps1 -Config …` (agrega `-Cloud` para ensayar desde la nube). Restaura el último respaldo en una base y una carpeta temporales y comprueba:
- el manifiesto: versión, filas por tabla y final de la cadena de auditoría;
- `alembic check`;
- `verify_images` (SHA-256 de cada archivo);
- `verify_audit`.

Al terminar borra lo temporal.

**Restauración real**, tras una falla. Es una operación manual y deliberada:
1. Detén la aplicación: `docker compose -f compose.prod.yml stop api proxy`.
2. Restaura con restic en una carpeta de trabajo: `restic -r <repo> --password-file <archivo> restore latest:/C/…/odontonet-backup-staging --target <carpeta>` y lo mismo para la carpeta de imágenes. `restic snapshots` lista los respaldos disponibles (con `--tag pre-migracion`, los previos a una actualización); usa su id en lugar de `latest` para restaurar uno concreto. Restaura cada carpeta con la sintaxis `snapshot:/ruta`: restaurar la ruta absoluta completa copia también los permisos de carpetas como `C:\Users`.
3. Recrea la base vacía dentro del contenedor y carga el volcado (usuario y base de `POSTGRES_USER` y `POSTGRES_DB` del `.env` de la raíz): `docker exec odontonet-db dropdb -U <usuario> <base>`, `docker exec odontonet-db createdb -U <usuario> <base>`, `docker cp odontonet.dump odontonet-db:/tmp/r.dump`, `docker exec odontonet-db pg_restore -U <usuario> -d <base> --no-owner /tmp/r.dump` y `docker exec odontonet-db rm /tmp/r.dump`.
4. Copia las imágenes a `IMAGE_STORAGE_DIR`.
5. Corre `python -m scripts.backup_manifest compare <manifest.json>`, `verify_images` y `verify_audit` antes de volver a abrir el sistema.
6. Borra la carpeta de trabajo: contiene datos sin cifrar.

## Ensayo documentado

| Fecha | Repositorio | Datos | Tiempo de respaldo | Tiempo de restauración | Ensayo completo | Resultado |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-08 | Local (desarrollo, restic 0.19.1) | Seed sintético: 81 pacientes, 123 citas, 2 imágenes (1,9 MiB) | 9 s | 2 s | 18 s | Correcto: manifiesto, esquema, imágenes y auditoría coinciden |
| 2026-11-08 | Local, tras la revisión (volcado y manifiesto del mismo snapshot, registros, limpieza del contenedor) | Mismo seed | 9 s | 2 s | 23 s | Correcto; sin volcados residuales en el contenedor ni en %TEMP% |

Con datos reales los tiempos crecen, sobre todo por las imágenes. Los respaldos siguientes son incrementales: restic solo sube lo que cambió.
