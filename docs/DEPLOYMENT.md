# Despliegue

Guía para instalar OdontoNet en una clínica. Cada clínica tiene su propia instalación, que funciona sin internet dentro de su red local.

## Ambientes

`APP_ENV` define el ambiente (`app/core/settings.py`):

| Valor | Uso | Comportamiento |
| --- | --- | --- |
| `development` (por defecto) | Trabajo local | `/docs` disponible; sin SMTP, los correos van al log |
| `test` | pytest | Exige una base `*_test` |
| `production` | Clínica | No arranca con configuración insegura; `/docs` apagado; sin SMTP, no se envían correos ni se registra su contenido |

## Arquitectura

Una instalación por clínica, con Docker Compose (`compose.prod.yml`):

| Servicio | Función | Acceso |
| --- | --- | --- |
| `proxy` (Caddy) | Sirve la interfaz, pasa `/api/*` a la API y termina HTTPS | Red de la clínica, puertos 80 y 443 |
| `api` (Uvicorn) | API, sin registro de accesos | Solo dentro de Docker |
| `db` (PostgreSQL 16) | Base de datos | Solo este equipo (`127.0.0.1`), para las herramientas de respaldo |

HTTPS funciona sin internet con una CA propia de Caddy. Por eso hay que instalar su certificado raíz en cada equipo que use el sistema. Los logs de los contenedores rotan (5 archivos de 10 MB) y nunca guardan la query string, porque las búsquedas llevan nombres de pacientes.

## Requisitos

- Windows con Docker Desktop, configurado para iniciar con la sesión. Los contenedores y las tareas de respaldo necesitan esa sesión abierta.
- Python 3.11 para las herramientas de respaldo.
- IP fija para el equipo servidor, asignada en el router.
- Una carpeta propia para la instalación (`git clone https://github.com/Czar272/OdontoNet`): no uses la copia de desarrollo. En un equipo con la base de desarrollo, quítala antes con `docker compose down`, **sin `-v`** para conservar sus datos: usan el mismo nombre de contenedor y puerto.
- Internet solo para instalar y actualizar (imágenes base y dependencias). Una vez instalado, el sistema funciona sin él.

## Configuración

```powershell
Copy-Item .env.production.example .env
Copy-Item backend/.env.production.example backend/.env
py -3.11 -m venv backend/odonto_venv
backend/odonto_venv/Scripts/python.exe -m pip install -r backend/requirements.txt
```

Reemplaza los valores de ambos archivos, que Git ignora. Los secretos solo viven ahí. La API los recibe de Docker Compose, que sustituye en el contenedor `DATABASE_URL` e `IMAGE_STORAGE_DIR`, y las herramientas de respaldo leen los mismos archivos desde el equipo.

En producción la API reporta todos los problemas juntos y no arranca si:
- `SECRET_KEY` o `DATABASE_URL` conservan un valor de ejemplo o de pruebas, o la base es `*_test`;
- `BCRYPT_ROUNDS` es menor que 12;
- `CORS_ORIGINS` tiene un origen sin https (vacía si todo se sirve desde un origen);
- `ALLOWED_HOSTS` no incluye el nombre real del servidor;
- `FRONTEND_URL` no es la dirección https real;
- `TRUST_PROXY_HEADERS` no es `true`;
- `IMAGE_STORAGE_DIR` no es una ruta absoluta.

El correo es opcional. Sin `SMTP_HOST`, la recuperación por correo no llega y administración asigna una contraseña nueva desde Usuarios.

## Instalar

1. Con los archivos listos:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\deploy\deploy.ps1 -FirstInstall
   ```

2. Crea la primera clínica. El comando pide la contraseña (10 caracteres o más, no común) y lo registra en la auditoría. Si ya hay una clínica, no cambia nada.

   ```powershell
   docker compose -f compose.prod.yml exec api python -m scripts.bootstrap_clinic --clinic-name "Nombre de la clínica" --admin-name "Nombre" --admin-email correo@ejemplo.com
   ```

3. Configura los respaldos (`BACKUPS.md`, «Puesta en marcha»). Van después de crear la clínica: el primer respaldo necesita la base ya migrada.
4. Permite los puertos 80 y 443 en el firewall de Windows, solo para la red privada.
5. **Comprueba la IP de los clientes.** Inicia sesión desde otro equipo y revisa `remote_ip` en `docker compose -f compose.prod.yml logs proxy`. Si aparece una IP interna de Docker en lugar de la del equipo, Docker Desktop la está ocultando y toda la clínica cuenta como una sola IP para el límite de intentos: sube `LOGIN_MAX_FAILURES_PER_IP` en `backend/.env` para que unos pocos errores no bloqueen a todos. El límite de 7 fallos por cuenta sigue funcionando.

## Conectar cada equipo de la clínica

1. **Nombre:** registra `odontonet.internal` con la IP del servidor en el DNS del router o, si no se puede, en `C:\Windows\System32\drivers\etc\hosts`.
2. **Certificado:** copia `deploy\odontonet-ca.crt` e instálalo, en una consola de administrador: `certutil -addstore -f Root odontonet-ca.crt`.
3. Abre `https://odontonet.internal`. Sin el certificado, el navegador muestra una advertencia.

El certificado raíz vive en el volumen `caddy_data`. Si se pierde, hay que repetir el paso 2 en cada equipo.

## Actualizar

```powershell
git pull
powershell -ExecutionPolicy Bypass -File scripts\deploy\deploy.ps1 -BackupConfig $env:USERPROFILE\.odontonet\backup.env
```

La API nunca migra sola: en producción, si la base no está en la última migración del código, no arranca. `deploy.ps1` detiene la aplicación, respalda, migra y la levanta de nuevo, y se detiene si el respaldo falla.

**Volver atrás tras una migración fallida:** la versión anterior del código no arranca con una base migrada, ni la nueva con la anterior, así que hay que revertir ambas.

1. Vuelve al commit anterior: `git checkout <commit>`.
2. Reconstruye sin levantar: `docker compose -f compose.prod.yml build`.
3. Restaura la base y las imágenes con la restauración real de `BACKUPS.md`, eligiendo el respaldo con `restic snapshots --tag pre-migracion`.
4. Levanta la aplicación: `docker compose -f compose.prod.yml up -d`.

## Pasar de la instalación de prueba a la definitiva

Después de la prueba de aceptación (`UAT.md`), y antes de registrar el primer paciente real, se retiran los datos ficticios y se instala desde cero en el mismo servidor (ODON-276). Es una operación deliberada, que borra datos. **Ensáyala antes en un equipo de prueba** y hazla con el acta de la UAT firmada, en un momento en que nadie use el sistema.

Qué se conserva y qué no:

| Elemento | Qué pasa | Por qué |
| --- | --- | --- |
| Base de datos (volumen `odontonet-prod_postgres_data`) | Se borra | Solo tiene datos ficticios |
| Carpeta de imágenes (`ODONTONET_IMAGE_DIR`) | Se vacía | Solo tiene fotos de tipodonto |
| Tareas programadas de respaldo | Se quitan y se vuelven a crear | Apuntan al repositorio de la UAT |
| Repositorio restic de la UAT y su contraseña | Se archivan o se borran (decide el responsable), **nunca se reutilizan** | Los respaldos reales no deben mezclarse con datos ficticios |
| CA de Caddy (volúmenes `odontonet-prod_caddy_data` y `odontonet-prod_caddy_config`) | **Se conservan** | Así no hay que reinstalar el certificado en cada equipo. Si se prefiere regenerarla, se borran también en el paso 4 y se repite P2 de la UAT en cada equipo |
| `.env` y `backend/.env` | Se conservan | Revisa que no queden valores de la prueba, como el nombre o el correo de la clínica ficticia |

**0. Apartar la configuración de respaldos de la UAT**, para que la definitiva no la sobrescriba. Mueve el `backup.env` y el archivo de contraseña que usó la UAT (sus rutas reales están en ese `backup.env`) a una carpeta propia:

```powershell
$uat = "$env:USERPROFILE\.odontonet\uat"
New-Item -ItemType Directory -Force $uat
Get-Content "$env:USERPROFILE\.odontonet\backup.env" | Select-String 'REPO|PASSWORD_FILE'   # anota las rutas de la UAT
Move-Item "$env:USERPROFILE\.odontonet\backup.env" "$uat\backup-uat.env"
Move-Item "$env:USERPROFILE\.odontonet\restic-password.txt" "$uat\restic-password-uat.txt"
```

Edita `$uat\backup-uat.env` para que `ODONTONET_BACKUP_PASSWORD_FILE` apunte a la nueva ruta de la contraseña. Si la UAT usó otros nombres, muévelos igual: lo importante es que en `%USERPROFILE%\.odontonet\` no quede ningún archivo de la UAT.

**1. Respaldo final de la UAT (opcional).** Si el responsable quiere conservar evidencia de la prueba:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup\backup.ps1 -Config $env:USERPROFILE\.odontonet\uat\backup-uat.env
```

Rotula el disco o la carpeta del repositorio como «UAT, datos ficticios», y no lo conectes como repositorio de la instalación definitiva.

**2. Quitar las tareas programadas de la UAT:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup\register-tasks.ps1 -Remove
```

**3. Detener la aplicación, sin borrar volúmenes.** No uses `down -v`: borraría también la CA.

```powershell
docker compose -f compose.prod.yml down
```

**4. Borrar solo el volumen de la base.** Lista los volúmenes y confirma el nombre exacto antes de borrar:

```powershell
docker volume ls --filter name=odontonet-prod_
docker volume rm odontonet-prod_postgres_data
```

Solo si se decidió **regenerar la CA**: `docker volume rm odontonet-prod_caddy_data odontonet-prod_caddy_config`. `deploy.ps1` exportará un `deploy\odontonet-ca.crt` nuevo en el paso 8, y habrá que instalarlo en cada equipo en el paso 11.

**5. Vaciar la carpeta de imágenes.** Primero muestra la ruta y compárala con `IMAGE_STORAGE_DIR` de `backend/.env`. Tiene que ser la carpeta de imágenes, nunca la del repositorio de respaldos:

```powershell
$dir = (Select-String -Path .env -Pattern '^ODONTONET_IMAGE_DIR=(.+)$').Matches[0].Groups[1].Value.Trim()
$dir; Test-Path -LiteralPath $dir
Select-String -Path backend\.env -Pattern '^IMAGE_STORAGE_DIR='
```

Si la ruta es la correcta, vacíala:

```powershell
Get-ChildItem -LiteralPath $dir -Force | Remove-Item -Recurse -Force
```

**6. Repositorio de la UAT.** Según lo que decida el responsable:
- **Archivarlo:** déjalo en su disco rotulado, junto con la carpeta `%USERPROFILE%\.odontonet\uat` (su configuración y su contraseña). Sin la contraseña no se puede leer.
- **Borrarlo:** borra su carpeta de repositorio y `%USERPROFILE%\.odontonet\uat`. En la nube, la UAT no debería haber usado un bucket; si lo usó, bórralo desde la consola del proveedor, porque el servidor no tiene permiso de borrado.

**7. Configurar los respaldos reales.** Sigue solo los **pasos 1 a 5** de «Puesta en marcha» de `BACKUPS.md`, con una contraseña nueva, un `backup.env` nuevo y repositorios nuevos: el local en el disco definitivo y, si se usa, la nube. El primer respaldo y las tareas van en el paso 10, cuando la base ya exista. Ninguna ruta de repositorio puede coincidir con la de la UAT.

**8. Instalar y crear la clínica real:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy\deploy.ps1 -FirstInstall
docker compose -f compose.prod.yml exec api python -m scripts.bootstrap_clinic --clinic-name "Nombre real" --admin-name "Nombre" --admin-email correo@clinica
```

`-FirstInstall` se niega a seguir si la base tiene datos: es una segunda protección por si el paso 4 no se hizo.

**9. Comprobar que la instalación quedó limpia**, antes de crear personal o pacientes:

```powershell
docker compose -f compose.prod.yml exec api python -m scripts.verify_fresh_install
```

Tiene que terminar con «Instalación limpia»: una clínica, un usuario, solo la auditoría del alta, cero filas en el resto de tablas y la carpeta de imágenes vacía. Si encuentra algo, no sigas: vuelve al paso 3.

**10. Primer respaldo, tareas y ensayo** (P4 de la UAT):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup\backup.ps1 -Config $env:USERPROFILE\.odontonet\backup.env -Init
powershell -ExecutionPolicy Bypass -File scripts\backup\register-tasks.ps1 -Config $env:USERPROFILE\.odontonet\backup.env -At 21:00
powershell -ExecutionPolicy Bypass -File scripts\backup\restore-check.ps1 -Config $env:USERPROFILE\.odontonet\backup.env
```

Después, **comprueba que no queda nada de la UAT en los respaldos**:

```powershell
restic -r <repositorio local definitivo> --password-file <contraseña definitiva> snapshots
Get-ScheduledTask -TaskName "OdontoNet*" | Select-Object -ExpandProperty Actions | Select-Object Arguments
```

- `snapshots` debe mostrar solo los respaldos de hoy (el del paso 10), ninguno anterior. Si usas la nube, repítelo con su repositorio.
- Los argumentos de las dos tareas deben nombrar el `backup.env` definitivo, no el de `uat\`.

**11. Comprobar desde cada equipo (P2 de la UAT).** Abre `https://odontonet.internal`: sin advertencia si se conservó la CA, y tras reinstalar el certificado si se regeneró.

**12. Registrar el paso** en el acta de la UAT (§7) o junto a ella:
- la fecha;
- el commit instalado;
- la salida del paso 9;
- la salida de `snapshots` y de las tareas del paso 10;
- qué se hizo con el repositorio de la UAT.

## Operación

```powershell
docker compose -f compose.prod.yml ps
docker compose -f compose.prod.yml logs --tail 100 api proxy
```

`https://odontonet.internal/api/health` indica si la API y la base responden.

## Probar el despliegue

`scripts/deploy/smoke.sh` levanta toda la pila en un proyecto aparte, con secretos desechables, comprueba HTTPS, cabeceras, base privada, sesión y logs, y borra solo lo que creó. Corre en CI en cada pull request y a mano. En Windows, desde Git Bash: `bash scripts/deploy/smoke.sh`.
