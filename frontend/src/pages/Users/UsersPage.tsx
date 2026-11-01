import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, UserCheck, UserX } from "lucide-react";
import toast from "react-hot-toast";

import Button from "../../components/basic/Button";
import ConfirmDialog from "../../components/basic/ConfirmDialog";
import Input from "../../components/basic/Input";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import Modal from "../../components/basic/Modal";
import PageHeader from "../../components/basic/PageHeader";
import Select from "../../components/basic/Select";
import Table from "../../components/basic/Table";
import UserForm from "../../components/users/UserForm";
import { useAuth } from "../../context/AuthContext";
import { getApiErrorMessage } from "../../services/apiError";
import { activateUser, deactivateUser, getUsers } from "../../services/userService";
import { ROLE_LABELS, type Role } from "../../types/auth";
import type { User } from "../../types/user";

const ROLES = Object.keys(ROLE_LABELS) as Role[];

/** null: modal cerrado · "new": alta · User: edición. */
type ModalState = null | "new" | User;

type StatusFilter = "" | "active" | "inactive";

const UsersPage: React.FC = () => {
  const { data: users, isLoading, isError } = useQuery({
    queryKey: ["users"],
    queryFn: () => getUsers(),
  });

  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();

  const [modal, setModal] = useState<ModalState>(null);
  const [toggling, setToggling] = useState<User | null>(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<Role | "">("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");

  const toggleMutation = useMutation({
    mutationFn: (user: User) =>
      user.is_active ? deactivateUser(user.id) : activateUser(user.id),

    onSuccess: (updated) => {
      toast.success(updated.is_active ? "Usuario activado" : "Usuario desactivado");
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["doctors"] });
      setToggling(null);
    },

    onError: (error) => {
      toast.error(getApiErrorMessage(error, "No se pudo cambiar el estado del usuario"));
    },
  });

  const filteredUsers = useMemo(() => {
    if (!users) return [];

    const term = search.trim().toLowerCase();

    return users.filter((u) => {
      const matchesSearch =
        u.name.toLowerCase().includes(term) || u.email.toLowerCase().includes(term);
      const matchesRole = !roleFilter || u.role === roleFilter;
      const matchesStatus =
        !statusFilter || u.is_active === (statusFilter === "active");

      return matchesSearch && matchesRole && matchesStatus;
    });
  }, [users, search, roleFilter, statusFilter]);

  if (isLoading) {
    return <LoadingSpinner />;
  }

  const closeModal = () => setModal(null);
  const editing = modal !== null && modal !== "new" ? modal : undefined;

  return (
    <div>
      <PageHeader
        title="Usuarios"
        description="Gestiona el personal con acceso a la clínica"
        action={<Button onClick={() => setModal("new")}>Nuevo usuario</Button>}
      />

      <div className="flex gap-4 mb-6">
        <div className="flex-1">
          <Input
            aria-label="Buscar usuarios"
            placeholder="Buscar por nombre o correo..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <Select
          aria-label="Filtrar por rol"
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value as Role | "")}
        >
          <option value="">Todos los roles</option>

          {ROLES.map((role) => (
            <option key={role} value={role}>
              {ROLE_LABELS[role]}
            </option>
          ))}
        </Select>

        <Select
          aria-label="Filtrar por estado"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
        >
          <option value="">Todos los estados</option>
          <option value="active">Activos</option>
          <option value="inactive">Inactivos</option>
        </Select>
      </div>

      <Modal
        isOpen={modal !== null}
        onClose={closeModal}
        title={editing ? "Editar usuario" : "Nuevo usuario"}
      >
        {/* key: reinicia el formulario al cambiar de usuario */}
        <UserForm key={editing?.id ?? "new"} user={editing} onSuccess={closeModal} />
      </Modal>

      <ConfirmDialog
        isOpen={toggling !== null}
        title={toggling?.is_active ? "Desactivar usuario" : "Activar usuario"}
        message={
          toggling?.is_active ? (
            <p>
              <strong>{toggling.name}</strong> ya no podrá iniciar sesión y su sesión
              actual se cerrará. Sus datos e historial se conservan y puedes volver a
              activarlo cuando quieras.
            </p>
          ) : (
            <p>
              <strong>{toggling?.name}</strong> podrá volver a iniciar sesión con su
              contraseña actual.
            </p>
          )
        }
        confirmLabel={toggling?.is_active ? "Desactivar" : "Activar"}
        variant={toggling?.is_active ? "danger" : "primary"}
        isPending={toggleMutation.isPending}
        onConfirm={() => toggling && toggleMutation.mutate(toggling)}
        onCancel={() => setToggling(null)}
      />

      <Table>
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left p-4">Nombre</th>

            <th className="text-left p-4">Correo</th>

            <th className="text-left p-4">Rol</th>

            <th className="text-left p-4">Estado</th>

            <th className="p-4">
              <span className="sr-only">Acciones</span>
            </th>
          </tr>
        </thead>

        <tbody>
          {filteredUsers.map((user) => (
            <tr key={user.id} className="border-t">
              <td className="p-4">{user.name}</td>

              <td className="p-4">{user.email}</td>

              <td className="p-4">{ROLE_LABELS[user.role] ?? user.role}</td>

              <td className="p-4">
                <span
                  className={
                    user.is_active
                      ? "px-2 py-1 rounded-lg text-xs bg-green-100 text-green-800"
                      : "px-2 py-1 rounded-lg text-xs bg-gray-200 text-gray-600"
                  }
                >
                  {user.is_active ? "Activo" : "Inactivo"}
                </span>
              </td>

              <td className="p-4 text-right whitespace-nowrap">
                <button
                  type="button"
                  onClick={() => setModal(user)}
                  aria-label={`Editar ${user.name}`}
                  title="Editar"
                  className="p-2 rounded-lg hover:bg-gray-100 transition"
                >
                  <Pencil size={18} />
                </button>

                {user.id !== currentUser?.id && (
                  <button
                    type="button"
                    onClick={() => setToggling(user)}
                    aria-label={`${user.is_active ? "Desactivar" : "Activar"} ${user.name}`}
                    title={user.is_active ? "Desactivar" : "Activar"}
                    className={
                      user.is_active
                        ? "p-2 rounded-lg text-red-600 hover:bg-red-50 transition"
                        : "p-2 rounded-lg text-green-700 hover:bg-green-50 transition"
                    }
                  >
                    {user.is_active ? <UserX size={18} /> : <UserCheck size={18} />}
                  </button>
                )}
              </td>
            </tr>
          ))}

          {filteredUsers.length === 0 && (
            <tr className="border-t">
              <td colSpan={5} className="p-6 text-center text-gray-500">
                {isError
                  ? "No se pudieron cargar los usuarios."
                  : "No hay usuarios que coincidan con la búsqueda."}
              </td>
            </tr>
          )}
        </tbody>
      </Table>
    </div>
  );
};

export default UsersPage;
