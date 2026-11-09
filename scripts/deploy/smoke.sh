#!/usr/bin/env bash
# Prueba de humo del despliegue de producción (ODON-238).
# Levanta la pila completa en un proyecto Compose propio, con secretos desechables,
# y comprueba lo que las pruebas unitarias no ven. Al terminar borra solo ese proyecto.
# Uso, desde la raíz del repositorio: bash scripts/deploy/smoke.sh
set -euo pipefail

PROJECT=odontonet-smoke
DOMAIN=odontonet.internal
HTTP_PORT=18080
HTTPS_PORT=18443
BASE="https://$DOMAIN:$HTTPS_PORT"
WORK=$(mktemp -d)
FAILURES=0

random() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "$1"; }

mkdir -p "$WORK/imagenes"
chmod 777 "$WORK/imagenes"
IMAGE_DIR="$WORK/imagenes"
API_ENV="$WORK/api.env"
# Git Bash en Windows: Docker necesita rutas de Windows.
if command -v cygpath >/dev/null; then
  IMAGE_DIR=$(cygpath -w "$IMAGE_DIR")
  API_ENV=$(cygpath -m "$API_ENV")
fi

DB_PASSWORD=$(random 32)
ADMIN_PASSWORD="Humo-$(random 24)"

cat > "$WORK/compose.env" <<EOF
POSTGRES_USER=odontonet
POSTGRES_PASSWORD=$DB_PASSWORD
POSTGRES_DB=odontonet
POSTGRES_PORT=15432
ODONTONET_DB_CONTAINER=odontonet-smoke-db
ODONTONET_DOMAIN=$DOMAIN
ODONTONET_HTTP_PORT=$HTTP_PORT
ODONTONET_HTTPS_PORT=$HTTPS_PORT
ODONTONET_IMAGE_DIR=$IMAGE_DIR
ODONTONET_API_ENV_FILE=$API_ENV
EOF

cat > "$WORK/api.env" <<EOF
APP_ENV=production
SECRET_KEY=$(random 48)
CORS_ORIGINS=
ALLOWED_HOSTS=$DOMAIN
FRONTEND_URL=$BASE
TRUST_PROXY_HEADERS=true
EOF

compose() { docker compose -p "$PROJECT" -f compose.prod.yml --env-file "$WORK/compose.env" "$@"; }

cleanup() {
  if [ "$FAILURES" -ne 0 ]; then compose logs --tail 40 || true; fi
  compose down --remove-orphans >/dev/null 2>&1 || true
  # Nombres exactos: solo los volúmenes desechables de esta prueba.
  docker volume rm "${PROJECT}_postgres_data" "${PROJECT}_caddy_data" "${PROJECT}_caddy_config" >/dev/null 2>&1 || true
  rm -rf "$WORK" 2>/dev/null || true
}
trap cleanup EXIT

http() { curl -sk --max-time 20 --resolve "$DOMAIN:$HTTPS_PORT:127.0.0.1" "$@"; }

check() { # descripción, valor obtenido, valor esperado
  if [ "$2" = "$3" ]; then
    echo "  ok    $1"
  else
    echo "  FALLA $1 (obtuve «$2», esperaba «$3»)"
    FAILURES=$((FAILURES + 1))
  fi
}

contains() { # descripción, texto, patrón
  if printf '%s' "$2" | grep -qiE "$3"; then
    echo "  ok    $1"
  else
    echo "  FALLA $1 (no aparece «$3»)"
    FAILURES=$((FAILURES + 1))
  fi
}

code() { http -o /dev/null -w '%{http_code}' "$@"; }

echo "Construyendo imágenes"
compose build --quiet

echo "Sin migrar, la API no debe arrancar"
compose up -d --wait db
compose up -d api >/dev/null 2>&1 || true
sleep 8
contains "la API reporta la base desactualizada" "$(compose logs api 2>&1)" "código espera"
compose stop api >/dev/null 2>&1 || true
compose rm -f api >/dev/null 2>&1 || true

echo "Migrando y creando la primera clínica"
compose run --rm -T api alembic upgrade head
compose run --rm -T -e BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_PASSWORD" api \
  python -m scripts.bootstrap_clinic --clinic-name "Clínica Humo" --admin-name "Administración" --admin-email admin@humo.example.com
compose up -d --wait

echo "Comprobando"
check "HTTP redirige a HTTPS" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -H "Host: $DOMAIN" "http://127.0.0.1:$HTTP_PORT/")" "308"
check "la interfaz responde" "$(code "$BASE/")" "200"
check "las rutas de la interfaz caen en index.html" "$(code "$BASE/patients/1")" "200"
HEADERS=$(http -D - -o /dev/null "$BASE/")
contains "HSTS" "$HEADERS" "strict-transport-security"
contains "CSP de la interfaz" "$HEADERS" "content-security-policy: default-src 'self'; script-src 'self'"
contains "index.html no se guarda en caché" "$HEADERS" "cache-control: no-cache"
check "/api/health" "$(http "$BASE/api/health")" '{"status":"ok","database":"ok"}'
API_HEADERS=$(http -D - -o /dev/null "$BASE/api/health")
contains "CSP estricta en la API" "$API_HEADERS" "content-security-policy: default-src 'none'"
contains "cache-control no-store en la API" "$API_HEADERS" "cache-control: no-store"
check "/docs apagado" "$(code "$BASE/api/docs")" "404"
check "/openapi.json apagado" "$(code "$BASE/api/openapi.json")" "404"
check "petición más grande que el límite" "$(head -c 12000000 /dev/zero | http -o /dev/null -w '%{http_code}' -X POST --data-binary @- "$BASE/api/auth/login")" "413"
contains "la base solo escucha en este equipo" "$(compose port db 5432)" "^127\.0\.0\.1:"

LOGIN=$(http -D - -c "$WORK/cookies" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@humo.example.com\",\"password\":\"$ADMIN_PASSWORD\"}" "$BASE/api/auth/login")
contains "login responde 200" "$LOGIN" "^HTTP/[0-9.]+ 200"
contains "cookie protegida" "$LOGIN" "set-cookie: odontonet_session=.*HttpOnly.*Path=/api/auth.*SameSite=strict.*Secure"
TOKEN=$(printf '%s' "$LOGIN" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
check "/auth/me con el token" "$(code -H "Authorization: Bearer $TOKEN" "$BASE/api/auth/me")" "200"
check "refresh con cookie y origen" "$(code -b "$WORK/cookies" -c "$WORK/cookies" -H "Origin: $BASE" -X POST "$BASE/api/auth/refresh")" "200"
check "refresh con origen ajeno" "$(code -b "$WORK/cookies" -H 'Origin: https://ajeno.example.com' -X POST "$BASE/api/auth/refresh")" "403"

http -o /dev/null -H "Authorization: Bearer $TOKEN" "$BASE/api/patients/?q=NombreReservado"
sleep 1
LOGS=$(compose logs api proxy 2>&1)
check "los logs no guardan búsquedas" "$(printf '%s' "$LOGS" | grep -c NombreReservado || true)" "0"
contains "el proxy registra las peticiones" "$LOGS" "/api/patients"

if [ "$FAILURES" -ne 0 ]; then
  echo "Prueba de humo: $FAILURES fallas"
  exit 1
fi
echo "Prueba de humo correcta"
