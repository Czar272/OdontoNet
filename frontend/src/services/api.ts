import axios from "axios";

import { getToken, notifyUnauthorized } from "./session";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000",
});

api.interceptors.request.use((config) => {
  const token = getToken();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

// Un 401 fuera del login significa que la sesión ya no es válida
// (token expirado, usuario desactivado...): se cierra la sesión.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 401 &&
      !error.config?.url?.includes("/auth/login")
    ) {
      notifyUnauthorized();
    }

    return Promise.reject(error);
  },
);

export default api;
