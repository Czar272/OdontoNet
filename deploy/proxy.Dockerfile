# Interfaz de OdontoNet servida por Caddy (ODON-238). Contexto de build: raíz del repositorio.
FROM node:22.23.3-alpine AS build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
# Sin VITE_API_URL: la interfaz llama a /api en su mismo origen.
RUN npm run build

FROM caddy:2.11.6-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /frontend/dist /srv
