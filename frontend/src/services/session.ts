/**
 * Almacenamiento del token y aviso de sesión inválida.
 *
 * Decisión vigente (ODON-52): el JWT se guarda en localStorage con expiración
 * corta y sin refresh token. Ver "Sesión" en docs/ARCHITECTURE.md.
 */
const TOKEN_KEY = "token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;

/** El AuthProvider registra aquí cómo cerrar la sesión ante un 401. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

export function notifyUnauthorized(): void {
  unauthorizedHandler?.();
}
