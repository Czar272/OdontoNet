"""Hosts permitidos (ODON-263).

Solo se atienden peticiones cuyo encabezado Host está en ALLOWED_HOSTS. Nació
como mitigación de Starlette PYSEC-2026-161; desde Starlette 1.x (ODON-264) se
mantiene como defensa adicional. A diferencia del TrustedHostMiddleware de
Starlette, responde con el formato de errores de la API, en español.
"""
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


def parse_allowed_hosts(raw: str) -> list[str]:
    """Lista de hosts separada por comas. Un comodín desactivaría la protección
    y una lista vacía rechazaría todo: ambos detienen el arranque."""
    hosts = [host.strip().lower() for host in raw.split(",") if host.strip()]
    if not hosts:
        raise RuntimeError("ALLOWED_HOSTS está vacía: indica los hosts de la API (por ejemplo, localhost,127.0.0.1).")
    if any("*" in host for host in hosts):
        raise RuntimeError("ALLOWED_HOSTS no admite '*': lista los hosts exactos de la API.")
    return hosts


def _host_without_port(value: str) -> str:
    value = value.strip().lower()
    if value.startswith("["):  # IPv6: [::1]:8000
        return value.split("]")[0] + "]"
    return value.split(":")[0]


class AllowedHostsMiddleware:
    def __init__(self, app: ASGIApp, allowed_hosts: list[str]) -> None:
        self.app = app
        self.allowed = set(allowed_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            host = _host_without_port(Headers(scope=scope).get("host", ""))
            if host not in self.allowed:
                response = JSONResponse({"detail": "Host no permitido."}, status_code=400)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
