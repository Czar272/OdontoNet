/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import toast from "react-hot-toast";

import { getApiErrorMessage } from "../services/apiError";
import { getCurrentUser, loginRequest } from "../services/authService";
import {
  clearToken,
  getToken,
  setToken,
  setUnauthorizedHandler,
} from "../services/session";
import type { CurrentUser } from "../types/auth";

/**
 * loading: hay token y se está verificando con /auth/me (evita parpadeos).
 * authenticated: sesión válida y usuario cargado.
 * unauthenticated: sin sesión.
 */
export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface AuthContextType {
  status: AuthStatus;
  user: CurrentUser | null;
  /** true si la sesión terminó por un cierre voluntario (no se recuerda la ruta anterior). */
  loggedOutManually: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
}

// Exportado para pruebas: permite simular una sesión sin llamar a la API.
export const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();

  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loggedOutManually, setLoggedOutManually] = useState(false);
  const [status, setStatus] = useState<AuthStatus>(() =>
    getToken() ? "loading" : "unauthenticated",
  );

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

  // Restaurar la sesión al cargar la aplicación.
  useEffect(() => {
    if (!getToken()) return;

    let cancelled = false;

    getCurrentUser()
      .then((currentUser) => {
        if (cancelled) return;
        setUser(currentUser);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        // Un 401 ya lo gestiona el interceptor. Otros errores (API caída):
        // se conserva el token para reintentar al recargar.
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

  const login = useCallback(async (email: string, password: string) => {
    try {
      const { access_token } = await loginRequest(email, password);
      setToken(access_token);

      const currentUser = await getCurrentUser();
      setUser(currentUser);
      setStatus("authenticated");
      setLoggedOutManually(false);

      toast.success(`Bienvenido, ${currentUser.name}`);
      return true;
    } catch (error) {
      // Sin console.error: el error de Axios incluye el cuerpo con la contraseña.
      clearToken();
      toast.error(getApiErrorMessage(error, "No se pudo iniciar sesión."));
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    setLoggedOutManually(true);
    clearSession();
    toast.success("Sesión cerrada");
  }, [clearSession]);

  return (
    <AuthContext.Provider value={{ status, user, loggedOutManually, login, logout }}>
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
