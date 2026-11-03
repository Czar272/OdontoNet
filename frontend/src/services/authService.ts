import api from "./api";

import type {
  CurrentUser,
  MessageResponse,
  TokenResponse,
} from "../types/auth";

export async function loginRequest(
  email: string,
  password: string,
  rememberMe = false,
): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>("/auth/login", {
    email,
    password,
    remember_me: rememberMe,
  });

  return response.data;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const response = await api.get<CurrentUser>("/auth/me");

  return response.data;
}

/** Pide el enlace de recuperación. Responde igual exista o no la cuenta. */
export async function requestPasswordReset(
  email: string,
): Promise<MessageResponse> {
  const response = await api.post<MessageResponse>(
    "/auth/password-reset/request",
    { email },
  );

  return response.data;
}

export async function confirmPasswordReset(
  token: string,
  newPassword: string,
): Promise<MessageResponse> {
  const response = await api.post<MessageResponse>(
    "/auth/password-reset/confirm",
    { token, new_password: newPassword },
  );

  return response.data;
}

/** Cambia la contraseña propia; devuelve un token nuevo para seguir en sesión. */
export async function changePasswordRequest(
  currentPassword: string,
  newPassword: string,
  rememberMe: boolean,
): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
    remember_me: rememberMe,
  });

  return response.data;
}
