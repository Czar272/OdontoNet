/**
 * Almacenamiento del token y aviso de sesión inválida.
 *
 * Decisión vigente (ODON-52, ajustada en ODON-255):
 * - Sin "Recuérdame": token corto en sessionStorage; se pierde al cerrar el navegador.
 * - Con "Recuérdame": token largo en localStorage; sobrevive al cierre del navegador.
 * Sin refresh token todavía (ODON-230). Ver "Sesión" en docs/ARCHITECTURE.md.
 */
const TOKEN_KEY = "token";

function safe<T>(action: () => T, fallback: T): T {
  try {
    return action();
  } catch {
    // Almacenamiento bloqueado (modo privado estricto, políticas del navegador).
    return fallback;
  }
}

export function getToken(): string | null {
  return safe(
    () => sessionStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(TOKEN_KEY),
    null,
  );
}

export function setToken(token: string, remember = false): void {
  clearToken();
  safe(() => (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token), undefined);
}

export function clearToken(): void {
  safe(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_KEY);
  }, undefined);
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
