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
import DoctorProfileForm from "../../components/doctors/DoctorProfileForm";
import { usePermission } from "../../hooks/usePermission";
import { getDoctors } from "../../services/doctorService";
import { getUsers } from "../../services/userService";
import { CLINICAL_PROFILE_ROLES } from "../../types/auth";
import type { Doctor } from "../../types/doctor";

type StatusFilter = "active" | "inactive" | "";

/** null: modal cerrado · "new": alta de perfil · Doctor: edición. */
type ModalState = null | "new" | Doctor;

/** Profesionales de la clínica. Todos los roles consultan; administración crea y edita perfiles. */
const DoctorsPage: React.FC = () => {
  const { data: doctors, isLoading, isError } = useQuery({
    queryKey: ["doctors"],
    queryFn: () => getDoctors(),
  });

  const canManage = usePermission("doctors:manage");

  // Usuarios que pueden tener perfil clínico (doctor o administración),
  // para ofrecer los que aún no lo tienen.
  const { data: users } = useQuery({
    queryKey: ["users"],
    queryFn: () => getUsers(),
    enabled: canManage,
  });

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("active");
  const [modal, setModal] = useState<ModalState>(null);

  const candidates = useMemo(() => {
    const withProfile = new Set(doctors?.map((d) => d.user_id));

    return (users ?? []).filter(
      (u) => CLINICAL_PROFILE_ROLES.includes(u.role) && !withProfile.has(u.id),
    );
  }, [doctors, users]);

  const filteredDoctors = useMemo(() => {
    if (!doctors) return [];

    const term = search.trim().toLowerCase();

    return doctors.filter((d) => {
      const text = `${d.user.name} ${d.specialization ?? ""}`.toLowerCase();
      const matchesStatus =
        !statusFilter || d.user.is_active === (statusFilter === "active");

      return text.includes(term) && matchesStatus;
    });
  }, [doctors, search, statusFilter]);

  if (isLoading) {
    return <LoadingSpinner />;
  }

  const closeModal = () => setModal(null);
  const editing = modal !== null && modal !== "new" ? modal : undefined;

  return (
    <div>
      <PageHeader
        title="Doctores"
        description="Profesionales de la clínica y su especialidad"
        action={
          canManage && <Button onClick={() => setModal("new")}>Nuevo perfil</Button>
        }
      />

      <Modal
        isOpen={modal !== null}
        onClose={closeModal}
        title={editing ? "Editar perfil" : "Nuevo perfil de doctor"}
      >
        <DoctorProfileForm
          key={editing?.id ?? "new"}
          doctor={editing}
          candidates={candidates}
          onSuccess={closeModal}
        />
      </Modal>

      <div className="flex gap-4 mb-6">
        <div className="flex-1">
          <Input
            aria-label="Buscar doctores"
            placeholder="Buscar por nombre o especialidad..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <Select
          aria-label="Filtrar por estado"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
        >
          <option value="active">Activos</option>
          <option value="inactive">Inactivos</option>
          <option value="">Todos</option>
        </Select>
      </div>

      <Table>
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left p-4">Nombre</th>

            <th className="text-left p-4">Especialidad</th>

            <th className="text-left p-4">Colegiado</th>

            <th className="text-left p-4">Teléfono</th>

            <th className="text-left p-4">Correo</th>

            <th className="text-left p-4">Estado</th>

            {canManage && (
              <th className="p-4">
                <span className="sr-only">Acciones</span>
              </th>
            )}
          </tr>
        </thead>

        <tbody>
          {filteredDoctors.map((doctor) => (
            <tr key={doctor.id} className="border-t">
              <td className="p-4">{doctor.user.name}</td>

              <td className="p-4">{doctor.specialization || "General"}</td>

              <td className="p-4">{doctor.license_number || "—"}</td>

              <td className="p-4">{doctor.phone || "—"}</td>

              <td className="p-4">{doctor.user.email}</td>

              <td className="p-4">
                <span
                  className={
                    doctor.user.is_active
                      ? "px-2 py-1 rounded-lg text-xs bg-green-100 text-green-800"
                      : "px-2 py-1 rounded-lg text-xs bg-gray-200 text-gray-600"
                  }
                >
                  {doctor.user.is_active ? "Activo" : "Inactivo"}
                </span>
              </td>

              {canManage && (
                <td className="p-4 text-right">
                  <button
                    type="button"
                    onClick={() => setModal(doctor)}
                    aria-label={`Editar perfil de ${doctor.user.name}`}
                    title="Editar perfil"
                    className="p-2 rounded-lg hover:bg-gray-100 transition"
                  >
                    <Pencil size={18} />
                  </button>
                </td>
              )}
            </tr>
          ))}

          {filteredDoctors.length === 0 && (
            <tr className="border-t">
              <td colSpan={canManage ? 7 : 6} className="p-6 text-center text-gray-500">
                {isError
                  ? "No se pudieron cargar los doctores."
                  : "No hay doctores que coincidan con la búsqueda."}
              </td>
            </tr>
          )}
        </tbody>
      </Table>
    </div>
  );
};

export default DoctorsPage;
