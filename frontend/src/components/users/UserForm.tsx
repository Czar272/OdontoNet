import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import Button from "../basic/Button";
import Input from "../basic/Input";
import Select from "../basic/Select";
import { useAuth } from "../../context/AuthContext";
import { getApiErrorMessage } from "../../services/apiError";
import { createUser, updateUser } from "../../services/userService";
import { ROLE_LABELS, type Role } from "../../types/auth";
import type { CreateUserDTO, User } from "../../types/user";
import {
  buildUserChanges,
  initialUserData,
  MIN_PASSWORD_LENGTH,
} from "./userFormData";

interface UserFormProps {
  /** Usuario a editar; sin él, el formulario crea uno nuevo. */
  user?: User;
  onSuccess?: () => void;
}

const ROLES = Object.keys(ROLE_LABELS) as Role[];

const UserForm: React.FC<UserFormProps> = ({ user, onSuccess }) => {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();

  const isEdit = Boolean(user);
  const isSelf = isEdit && user?.id === currentUser?.id;

  const [formData, setFormData] = useState<CreateUserDTO>(() =>
    initialUserData(user),
  );

  const mutation = useMutation({
    mutationFn: (data: CreateUserDTO) =>
      user
        ? updateUser(user.id, buildUserChanges(user, data))
        : createUser(data),

    onSuccess: () => {
      toast.success(isEdit ? "Usuario actualizado" : "Usuario creado");
      queryClient.invalidateQueries({ queryKey: ["users"] });
      // Nombres de doctores en listados y filtros.
      queryClient.invalidateQueries({ queryKey: ["doctors"] });
      setFormData(initialUserData(user));
      onSuccess?.();
    },

    onError: (error) => {
      toast.error(
        getApiErrorMessage(
          error,
          isEdit
            ? "No se pudo actualizar el usuario"
            : "No se pudo crear el usuario",
        ),
      );
    },
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (user && Object.keys(buildUserChanges(user, formData)).length === 0) {
      toast("No hay cambios que guardar");
      return;
    }

    mutation.mutate(formData);
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          name="name"
          label="Nombre completo *"
          value={formData.name}
          onChange={handleChange}
          maxLength={120}
          required
        />

        <Input
          name="email"
          type="email"
          label="Correo electrónico *"
          value={formData.email}
          onChange={handleChange}
          autoComplete="off"
          required
        />

        <div className="flex flex-col gap-1">
          <Select
            name="role"
            label="Rol *"
            value={formData.role}
            onChange={handleChange}
            disabled={isSelf}
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {ROLE_LABELS[role]}
              </option>
            ))}
          </Select>

          {isSelf && (
            <p className="text-xs text-gray-500">
              No puedes cambiar tu propio rol.
            </p>
          )}
        </div>

        {isSelf ? (
          <p className="text-xs text-gray-500">
            Para cambiar tu propia contraseña usa «Cambiar contraseña» en el
            menú.
          </p>
        ) : (
          <div className="flex flex-col gap-1">
            <Input
              name="password"
              type="password"
              label={isEdit ? "Nueva contraseña" : "Contraseña *"}
              value={formData.password}
              onChange={handleChange}
              minLength={MIN_PASSWORD_LENGTH}
              maxLength={128}
              autoComplete="new-password"
              required={!isEdit}
            />

            <p className="text-xs text-gray-500">
              {isEdit
                ? "Déjala vacía para conservar la actual."
                : `Mínimo ${MIN_PASSWORD_LENGTH} caracteres.`}
            </p>
          </div>
        )}
      </div>

      <div className="mt-6 flex justify-end">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending
            ? "Guardando..."
            : isEdit
              ? "Guardar cambios"
              : "Crear usuario"}
        </Button>
      </div>
    </form>
  );
};

export default UserForm;
