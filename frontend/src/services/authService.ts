import api from "./api";

import type { CurrentUser } from "../types/auth";

export async function getCurrentUser(): Promise<CurrentUser> {
  const response = await api.get("/auth/me");

  return response.data;
}
