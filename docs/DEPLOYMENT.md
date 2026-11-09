# Despliegue

Guía para instalar OdontoNet en una clínica. Cada clínica tiene su propia instalación, que funciona sin internet dentro de su red local.

## Ambientes

`APP_ENV` define el ambiente (`app/core/settings.py`):

| Valor | Uso | Comportamiento |
| --- | --- | --- |
| `development` (por defecto) | Trabajo local | `/docs` disponible; sin SMTP, los correos van al log |
| `test` | pytest | Exige una base `*_test` |
| `production` | Clínica | No arranca con configuración insegura; `/docs` apagado; sin SMTP, no se envían correos ni se registra su contenido |

## Configuración

Copia `backend/.env.production.example` a `backend/.env.production` (Git lo ignora) y reemplaza los valores. Los secretos solo viven en ese archivo. La aplicación no lo lee por su nombre: Docker Compose carga sus variables en el contenedor de la API, y los comandos de administración corren dentro de ese contenedor.

En producción la API reporta todos los problemas juntos y no arranca si:
- `SECRET_KEY` o `DATABASE_URL` conservan un valor de ejemplo o de pruebas, o la base es `*_test`;
- `BCRYPT_ROUNDS` es menor que 12;
- `CORS_ORIGINS` tiene un origen sin https (vacía si todo se sirve desde un origen);
- `ALLOWED_HOSTS` no incluye el nombre real del servidor;
- `FRONTEND_URL` no es la dirección https real;
- `TRUST_PROXY_HEADERS` no es `true`;
- `IMAGE_STORAGE_DIR` no es una ruta absoluta.

El correo es opcional. Sin `SMTP_HOST`, la recuperación por correo no llega y administración asigna una contraseña nueva desde Personal.

## Migraciones

La API nunca migra sola. En producción, si la base no está en la última migración del código, no arranca. Las migraciones se aplican solo con el procedimiento de despliegue, que respalda antes.

## Primera clínica

Con la base vacía y las migraciones aplicadas:

```powershell
python -m scripts.bootstrap_clinic --clinic-name "Nombre de la clínica" --admin-name "Nombre" --admin-email correo@ejemplo.com
```

El comando pide la contraseña (10 caracteres o más, no común), crea la clínica y su administración, y lo registra en la auditoría. Si ya hay una clínica, no cambia nada.
