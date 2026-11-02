import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import Button from "../../components/basic/Button";
import Input from "../../components/basic/Input";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import Modal from "../../components/basic/Modal";
import PageHeader from "../../components/basic/PageHeader";
import Select from "../../components/basic/Select";
import Table from "../../components/basic/Table";
import PatientForm from "../../components/patients/PatientForm";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { usePermission } from "../../hooks/usePermission";
import { getDoctors } from "../../services/doctorService";
import { getPatients } from "../../services/patientService";

const PAGE_SIZE = 20;

type StatusFilter = "active" | "archived";

const PatientsPage: React.FC = () => {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("active");
  const [search, setSearch] = useState("");
  const [doctorFilter, setDoctorFilter] = useState<number | undefined>();
  const [page, setPage] = useState(1);

  const archived = statusFilter === "archived";
  // Se consulta al backend cuando se deja de escribir, no en cada tecla.
  const debouncedSearch = useDebouncedValue(search.trim(), 300);

  // Búsqueda, filtros y paginación se resuelven en el backend (ODON-126).
  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: [
      "patients",
      "list",
      { archived, search: debouncedSearch, doctorFilter, page },
    ],
    queryFn: () =>
      getPatients({
        archived,
        search: debouncedSearch,
        doctorId: doctorFilter,
        page,
        pageSize: PAGE_SIZE,
      }),
    // Mantiene la página anterior visible mientras llega la siguiente.
    placeholderData: keepPreviousData,
  });

  // Todos los doctores, incluidos inactivos: sus pacientes siguen en el historial.
  const { data: doctors } = useQuery({
    queryKey: ["doctors"],
    queryFn: () => getDoctors(),
  });

  const canCreate = usePermission("patients:create");

  const [isModalOpen, setIsModalOpen] = useState(false);

  if (isLoading) {
    return <LoadingSpinner />;
  }

  const patients = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters = Boolean(debouncedSearch || doctorFilter);

  // Cambiar un filtro vuelve a la primera página.
  const changeFilter = (apply: () => void) => {
    apply();
    setPage(1);
  };

  const clearFilters = () =>
    changeFilter(() => {
      setSearch("");
      setDoctorFilter(undefined);
    });

  return (
    <div>
      <PageHeader
        title="Pacientes"
        description="Gestiona los pacientes de la clínica"
        action={
          canCreate && (
            <Button onClick={() => setIsModalOpen(true)}>Nuevo paciente</Button>
          )
        }
      />

      <div className="flex gap-4 mb-6">
        <div className="flex-1">
          <Input
            aria-label="Buscar pacientes"
            placeholder="Buscar por nombre, correo o teléfono..."
            value={search}
            maxLength={100}
            onChange={(e) => changeFilter(() => setSearch(e.target.value))}
          />
        </div>

        <Select
          aria-label="Filtrar por doctor"
          value={doctorFilter ?? ""}
          onChange={(e) =>
            changeFilter(() =>
              setDoctorFilter(
                e.target.value ? Number(e.target.value) : undefined,
              ),
            )
          }
        >
          <option value="">Todos los doctores</option>

          {doctors?.map((doctor) => (
            <option key={doctor.id} value={doctor.id}>
              {doctor.user.name}
              {doctor.user.is_active ? "" : " (inactivo)"}
            </option>
          ))}
        </Select>

        <Select
          aria-label="Filtrar por estado"
          value={statusFilter}
          onChange={(e) =>
            changeFilter(() => setStatusFilter(e.target.value as StatusFilter))
          }
        >
          <option value="active">Activos</option>
          <option value="archived">Archivados</option>
        </Select>
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Nuevo paciente"
      >
        <PatientForm onSuccess={() => setIsModalOpen(false)} />
      </Modal>

      <Table>
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left p-4">Nombre</th>

            <th className="text-left p-4">Correo</th>

            <th className="text-left p-4">Teléfono</th>

            <th className="text-left p-4">Doctor</th>
          </tr>
        </thead>

        <tbody
          className={isFetching ? "opacity-60 transition-opacity" : undefined}
        >
          {patients.map((patient) => (
            <tr key={patient.id} className="border-t">
              <td className="p-4">
                <Link
                  to={`/patients/${patient.id}`}
                  className="font-medium hover:underline"
                >
                  {patient.first_name} {patient.last_name}
                </Link>

                {patient.archived_at && (
                  <span className="ml-2 px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-800">
                    Archivado
                  </span>
                )}
              </td>

              <td className="p-4">{patient.email ?? "—"}</td>

              <td className="p-4">{patient.phone ?? "—"}</td>

              <td className="p-4">
                {patient.doctor?.user.name ?? "Sin asignar"}
              </td>
            </tr>
          ))}

          {patients.length === 0 && (
            <tr className="border-t">
              <td colSpan={4} className="p-6 text-center text-gray-500">
                {isError ? (
                  "No se pudieron cargar los pacientes."
                ) : hasFilters ? (
                  <>
                    No hay pacientes que coincidan con la búsqueda.{" "}
                    <button
                      type="button"
                      onClick={clearFilters}
                      className="underline text-gray-700 hover:text-gray-900"
                    >
                      Limpiar filtros
                    </button>
                  </>
                ) : total > 0 ? (
                  "No hay pacientes en esta página."
                ) : archived ? (
                  "No hay pacientes archivados."
                ) : (
                  "Todavía no hay pacientes registrados en la clínica."
                )}
              </td>
            </tr>
          )}
        </tbody>
      </Table>

      {total > 0 && (
        <nav
          aria-label="Paginación de pacientes"
          className="mt-4 flex items-center justify-between text-sm text-gray-600"
        >
          <span>
            {total === 1 ? "1 paciente" : `${total} pacientes`} · Página{" "}
            {data?.page ?? page} de {totalPages}
          </span>

          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => setPage((p) => p - 1)}
              disabled={page <= 1 || isFetching}
            >
              Anterior
            </Button>

            <Button
              variant="secondary"
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= totalPages || isFetching}
            >
              Siguiente
            </Button>
          </div>
        </nav>
      )}
    </div>
  );
};

export default PatientsPage;
