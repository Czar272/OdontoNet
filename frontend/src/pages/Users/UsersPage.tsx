import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pencil } from "lucide-react";

import Button from "../../components/basic/Button";
import Input from "../../components/basic/Input";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import Modal from "../../components/basic/Modal";
import PageHeader from "../../components/basic/PageHeader";
import Select from "../../components/basic/Select";
import Table from "../../components/basic/Table";
import UserForm from "../../components/users/UserForm";
import { getUsers } from "../../services/userService";
import { ROLE_LABELS, type Role } from "../../types/auth";
import type { User } from "../../types/user";

const ROLES = Object.keys(ROLE_LABELS) as Role[];

/** null: modal cerrado · "new": alta · User: edición. */
type ModalState = null | "new" | User;

const UsersPage: React.FC = () => {
  const { data: users, isLoading, isError } = useQuery({
    queryKey: ["users"],
    queryFn: () => getUsers(),
  });

  const [modal, setModal] = useState<ModalState>(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<Role | "">("");

  const filteredUsers = useMemo(() => {
    if (!users) return [];

    const term = search.trim().toLowerCase();

    return users.filter((u) => {
      const matchesSearch =
        u.name.toLowerCase().includes(term) || u.email.toLowerCase().includes(term);
      const matchesRole = !roleFilter || u.role === roleFilter;

      return matchesSearch && matchesRole;
    });
  }, [users, search, roleFilter]);

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
      </div>

      <Modal
        isOpen={modal !== null}
        onClose={closeModal}
        title={editing ? "Editar usuario" : "Nuevo usuario"}
      >
        {/* key: reinicia el formulario al cambiar de usuario */}
        <UserForm key={editing?.id ?? "new"} user={editing} onSuccess={closeModal} />
      </Modal>

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

              <td className="p-4 text-right">
                <button
                  type="button"
                  onClick={() => setModal(user)}
                  aria-label={`Editar ${user.name}`}
                  className="p-2 rounded-lg hover:bg-gray-100 transition"
                >
                  <Pencil size={18} />
                </button>
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
