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
  safe(
    () => (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token),
    undefined,
  );
}

/** true si la sesión actual usa "Recuérdame" (token en localStorage). */
export function isRememberedSession(): boolean {
  return safe(
    () =>
      sessionStorage.getItem(TOKEN_KEY) === null &&
      localStorage.getItem(TOKEN_KEY) !== null,
    false,
  );
}

/** Sustituye el token conservando dónde se guarda (p. ej. tras cambiar la contraseña). */
export function replaceToken(token: string): void {
  setToken(token, isRememberedSession());
}

/** Prefijo de los respaldos locales con datos clínicos (p. ej. periodontograma). */
export const CLINICAL_DRAFT_PREFIX = "odontonet:periodontal-draft:";

/** Borra los respaldos clínicos que la sesión dejó en el navegador. */
export function clearSessionDrafts(): void {
  safe(() => {
    for (const key of Object.keys(sessionStorage)) {
      if (key.startsWith(CLINICAL_DRAFT_PREFIX)) sessionStorage.removeItem(key);
    }
  }, undefined);
}

export function clearToken(): void {
  safe(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_KEY);
  }, undefined);
  // Al cerrar sesión (voluntaria o por 401) no quedan datos clínicos en la pestaña.
  clearSessionDrafts();
}

type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;

/** El AuthProvider registra aquí cómo cerrar la sesión ante un 401. */
export function setUnauthorizedHandler(
  handler: UnauthorizedHandler | null,
): void {
  unauthorizedHandler = handler;
}

export function notifyUnauthorized(): void {
  unauthorizedHandler?.();
}
