import type { Role } from "../types/auth";
import type { CreateUserDTO, UpdateUserDTO, User } from "../types/user";
import api from "./api";

export async function getUsers(role?: Role): Promise<User[]> {
  const response = await api.get("/users/", { params: role ? { role } : {} });

  return response.data;
}

export async function createUser(user: CreateUserDTO): Promise<User> {
  const response = await api.post("/users/", user);

  return response.data;
}

export async function updateUser(id: number, changes: UpdateUserDTO): Promise<User> {
  const response = await api.patch(`/users/${id}`, changes);

  return response.data;
}
