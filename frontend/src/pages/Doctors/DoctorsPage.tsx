import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import Input from "../../components/basic/Input";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import PageHeader from "../../components/basic/PageHeader";
import Select from "../../components/basic/Select";
import Table from "../../components/basic/Table";
import { getDoctors } from "../../services/doctorService";

type StatusFilter = "active" | "inactive" | "";

/** Profesionales de la clínica. Todos los roles consultan; el alta del perfil es ODON-90. */
const DoctorsPage: React.FC = () => {
  const { data: doctors, isLoading, isError } = useQuery({
    queryKey: ["doctors"],
    queryFn: () => getDoctors(),
  });

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("active");

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

  return (
    <div>
      <PageHeader
        title="Doctores"
        description="Profesionales de la clínica y su especialidad"
      />

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
            </tr>
          ))}

          {filteredDoctors.length === 0 && (
            <tr className="border-t">
              <td colSpan={6} className="p-6 text-center text-gray-500">
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
