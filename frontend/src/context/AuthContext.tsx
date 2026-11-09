/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import toast from "react-hot-toast";

import { refreshSession } from "../services/api";
import { getApiErrorMessage } from "../services/apiError";
import { getCurrentUser, loginRequest, logoutRequest } from "../services/authService";
import {
  announceSession,
  clearToken,
  getSessionUserId,
  getToken,
  onSessionAnnounced,
  setToken,
  setUnauthorizedHandler,
} from "../services/session";
import type { CurrentUser } from "../types/auth";

/**
 * loading: se está comprobando si hay una sesión (evita parpadeos).
 * authenticated: sesión válida y usuario cargado.
 * unauthenticated: sin sesión.
 */
export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface AuthContextType {
  status: AuthStatus;
  user: CurrentUser | null;
  /** true si la sesión terminó por un cierre voluntario (no se recuerda la ruta anterior). */
  loggedOutManually: boolean;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<boolean>;
  logout: () => void;
  /** Vuelve a leer /auth/me (por ejemplo, tras renombrar la clínica). */
  refreshUser: () => Promise<void>;
}

// Exportado para pruebas: permite simular una sesión sin llamar a la API.
export const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();

  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loggedOutManually, setLoggedOutManually] = useState(false);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const clearSession = useCallback(() => {
    clearToken();
    setUser(null);
    setStatus("unauthenticated");
    // Ningún dato de la sesión anterior debe quedar visible.
    queryClient.clear();
  }, [queryClient]);

  // Cualquier 401 de la API (token expirado, usuario desactivado) cierra la sesión.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setLoggedOutManually(false);
      if (getToken()) {
        toast.error("Tu sesión expiró. Inicia sesión de nuevo.", {
          id: "session-expired",
        });
      }
      clearSession();
    });

    return () => setUnauthorizedHandler(null);
  }, [clearSession]);

  // Otra pestaña cerró la sesión o entró con otra cuenta: esta deja de mostrar
  // y de guardar datos a nombre de la anterior.
  useEffect(
    () =>
      onSessionAnnounced((userId) => {
        if (userId === getSessionUserId()) return;
        setLoggedOutManually(userId === null);
        clearSession();
      }),
    [clearSession],
  );

  // Restaurar la sesión al cargar la aplicación, con la cookie httpOnly.
  useEffect(() => {
    let cancelled = false;

    refreshSession()
      .then(async (token) => {
        if (!token) {
          if (!cancelled) setStatus("unauthenticated");
          return;
        }
        const currentUser = await getCurrentUser();
        if (cancelled) return;
        setUser(currentUser);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        // Un 401 ya lo gestiona el interceptor. Otros errores (API caída):
        // la cookie se conserva para reintentar al recargar.
        if (!(axios.isAxiosError(error) && error.response?.status === 401)) {
          toast.error("No se pudo conectar con el servidor.", {
            id: "server-unavailable",
          });
          setStatus("unauthenticated");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string, rememberMe = false) => {
    try {
      const { access_token, user_id } = await loginRequest(email, password, rememberMe);
      setToken(access_token, user_id);

      const currentUser = await getCurrentUser();
      setUser(currentUser);
      setStatus("authenticated");
      setLoggedOutManually(false);
      announceSession(user_id);

      toast.success(`Bienvenido, ${currentUser.name}`);
      return true;
    } catch (error) {
      // Sin console.error: el error de Axios incluye el cuerpo con la contraseña.
      // Si el login funcionó pero falló lo siguiente, no debe quedar sesión abierta.
      if (getToken()) logoutRequest().catch(() => undefined);
      clearToken();
      toast.error(getApiErrorMessage(error, "No se pudo iniciar sesión."));
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    // JavaScript no puede borrar la cookie: hasta que el servidor confirme, la
    // sesión sigue abierta, y mostrar el login sería engañoso en un equipo compartido.
    logoutRequest().then(
      () => {
        setLoggedOutManually(true);
        clearSession();
        announceSession(null);
        toast.success("Sesión cerrada");
      },
      () => toast.error("No se pudo cerrar la sesión. Revisa la conexión e inténtalo de nuevo."),
    );
  }, [clearSession]);

  const refreshUser = useCallback(async () => {
    // Un 401 aquí lo gestiona el interceptor; otros errores no cierran la sesión.
    try {
      setUser(await getCurrentUser());
    } catch {
      /* se conserva el usuario actual */
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{ status, user, loggedOutManually, login, logout, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth debe usarse dentro de AuthProvider");
  }

  return context;
}
