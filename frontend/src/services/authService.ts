import api from "./api";

import type { CurrentUser, TokenResponse } from "../types/auth";

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
