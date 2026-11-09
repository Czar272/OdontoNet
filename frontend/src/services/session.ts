/**
 * Token de acceso y aviso de sesión inválida (ODON-265).
 *
 * El token de acceso vive solo en memoria: un script no lo encuentra en el
 * almacenamiento del navegador y se pierde al recargar. La sesión se recupera
 * con el refresh token, en una cookie httpOnly que JavaScript no puede leer.
 * Ver "Sesión y tokens" en docs/ARCHITECTURE.md.
 */
const LEGACY_TOKEN_KEY = "token";

let accessToken: string | null = null;

function safe<T>(action: () => T, fallback: T): T {
  try {
    return action();
  } catch {
    // Almacenamiento bloqueado (modo privado estricto, políticas del navegador).
    return fallback;
  }
}

// Las versiones anteriores guardaban el token en el navegador: no debe quedar ahí.
safe(() => {
  sessionStorage.removeItem(LEGACY_TOKEN_KEY);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
}, undefined);

export function getToken(): string | null {
  return accessToken;
}

export function setToken(token: string): void {
  accessToken = token;
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
  accessToken = null;
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
