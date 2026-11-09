import axios, { type InternalAxiosRequestConfig } from "axios";

import type { TokenResponse } from "../types/auth";
import { getToken, notifyUnauthorized, setToken } from "./session";

const api = axios.create({
  // Mismo origen que la interfaz: la cookie de sesión es SameSite=Strict.
  baseURL: import.meta.env.VITE_API_URL ?? "/api",
});

api.interceptors.request.use((config) => {
  const token = getToken();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

let pendingRefresh: Promise<string | null> | null = null;

async function requestNewToken(): Promise<string | null> {
  try {
    const { data } = await api.post<TokenResponse>("/auth/refresh");
    setToken(data.access_token);
    return data.access_token;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) return null;
    throw error;
  }
}

/**
 * Pide un token de acceso con la cookie de sesión; null si no hay sesión válida.
 * Una sola renovación a la vez: entre peticiones de esta pestaña se comparte la
 * misma promesa, y entre pestañas se ordena con Web Locks donde exista.
 */
export function refreshSession(): Promise<string | null> {
  pendingRefresh ??= (
    "locks" in navigator
      ? navigator.locks.request("odontonet-session-refresh", requestNewToken)
      : requestNewToken()
  ).finally(() => {
    pendingRefresh = null;
  });

  return pendingRefresh;
}

const SESSION_ROUTES = ["/auth/login", "/auth/refresh", "/auth/logout"];

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

// Un 401 fuera de las rutas de sesión significa que venció el token de acceso:
// se renueva una vez y se repite la petición. Si no se puede, se cierra la sesión.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (!axios.isAxiosError(error) || error.response?.status !== 401) {
      return Promise.reject(error);
    }

    const config = error.config as RetriableConfig | undefined;

    if (!config || SESSION_ROUTES.some((route) => config.url?.includes(route))) {
      return Promise.reject(error);
    }

    if (config._retried) {
      notifyUnauthorized();
      return Promise.reject(error);
    }

    let token: string | null;
    try {
      token = await refreshSession();
    } catch {
      // Servidor inalcanzable: no es motivo para cerrar la sesión.
      return Promise.reject(error);
    }

    if (!token) {
      notifyUnauthorized();
      return Promise.reject(error);
    }

    config._retried = true;
    return api(config);
  },
);

export default api;
