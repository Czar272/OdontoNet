import api from "./api";

import type { CurrentUser, TokenResponse } from "../types/auth";

export async function loginRequest(
  email: string,
  password: string,
): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>("/auth/login", {
    email,
    password,
  });

  return response.data;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const response = await api.get<CurrentUser>("/auth/me");

  return response.data;
}
