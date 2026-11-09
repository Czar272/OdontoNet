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
- Una carpeta propia para la instalación: no uses la copia de desarrollo. En un equipo con la base de desarrollo en marcha, detenla antes con `docker compose stop` (usan el mismo contenedor y puerto).

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

El correo es opcional. Sin `SMTP_HOST`, la recuperación por correo no llega y administración asigna una contraseña nueva desde Personal.

## Instalar

1. Configura los respaldos (`BACKUPS.md`).
2. Con los archivos listos:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\deploy\deploy.ps1 -FirstInstall
   ```

3. Crea la primera clínica. El comando pide la contraseña (10 caracteres o más, no común) y lo registra en la auditoría. Si ya hay una clínica, no cambia nada.

   ```powershell
   docker compose -f compose.prod.yml exec api python -m scripts.bootstrap_clinic --clinic-name "Nombre de la clínica" --admin-name "Nombre" --admin-email correo@ejemplo.com
   ```

4. Permite los puertos 80 y 443 en el firewall de Windows, solo para la red privada.

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

La API nunca migra sola: en producción, si la base no está en la última migración del código, no arranca. `deploy.ps1` respalda, detiene la API, migra y la levanta de nuevo, y se detiene si el respaldo falla. Para volver atrás tras una migración fallida, restaura el respaldo `pre-migracion` (`BACKUPS.md`).

## Operación

```powershell
docker compose -f compose.prod.yml ps
docker compose -f compose.prod.yml logs --tail 100 api proxy
```

`https://odontonet.internal/api/health` indica si la API y la base responden.

## Probar el despliegue

`scripts/deploy/smoke.sh` levanta toda la pila en un proyecto aparte, con secretos desechables, comprueba HTTPS, cabeceras, base privada, sesión y logs, y borra solo lo que creó. Corre en CI en cada pull request y a mano. En Windows, desde Git Bash: `bash scripts/deploy/smoke.sh`.
