import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import Button from "../../components/basic/Button";
import Input from "../../components/basic/Input";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import Modal from "../../components/basic/Modal";
import PageHeader from "../../components/basic/PageHeader";
import Select from "../../components/basic/Select";
import Table from "../../components/basic/Table";
import PatientForm from "../../components/patients/PatientForm";
import { usePermission } from "../../hooks/usePermission";
import { getDoctors } from "../../services/doctorService";
import { getPatients } from "../../services/patientService";

/** Minúsculas y sin tildes: "jose" encuentra a "José". */
function normalize(text: string): string {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

const PatientsPage: React.FC = () => {
  const { data: patients, isLoading, isError } = useQuery({
    queryKey: ["patients"],
    queryFn: getPatients,
  });

  // Todos los doctores, incluidos inactivos: sus pacientes siguen en el historial.
  const { data: doctors } = useQuery({
    queryKey: ["doctors"],
    queryFn: () => getDoctors(),
  });

  const canCreate = usePermission("patients:create");

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [doctorFilter, setDoctorFilter] = useState<number | undefined>();

  const filteredPatients = useMemo(() => {
    if (!patients) return [];

    const term = normalize(search.trim());

    return patients.filter((p) => {
      const fullName = normalize(`${p.first_name} ${p.last_name}`);
      const reversed = normalize(`${p.last_name} ${p.first_name}`);
      const matchesSearch = fullName.includes(term) || reversed.includes(term);
      const matchesDoctor = !doctorFilter || p.doctor?.id === doctorFilter;

      return matchesSearch && matchesDoctor;
    });
  }, [patients, search, doctorFilter]);

  if (isLoading) {
    return <LoadingSpinner />;
  }

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
            placeholder="Buscar por nombre..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <Select
          aria-label="Filtrar por doctor"
          value={doctorFilter ?? ""}
          onChange={(e) =>
            setDoctorFilter(e.target.value ? Number(e.target.value) : undefined)
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

        <tbody>
          {filteredPatients.map((patient) => (
            <tr key={patient.id} className="border-t">
              <td className="p-4">
                <Link
                  to={`/patients/${patient.id}`}
                  className="font-medium hover:underline"
                >
                  {patient.first_name} {patient.last_name}
                </Link>
              </td>

              <td className="p-4">{patient.email ?? "—"}</td>

              <td className="p-4">{patient.phone ?? "—"}</td>

              <td className="p-4">{patient.doctor?.user.name ?? "Sin asignar"}</td>
            </tr>
          ))}

          {filteredPatients.length === 0 && (
            <tr className="border-t">
              <td colSpan={4} className="p-6 text-center text-gray-500">
                {isError ? (
                  "No se pudieron cargar los pacientes."
                ) : patients && patients.length > 0 ? (
                  <>
                    No hay pacientes que coincidan con la búsqueda.{" "}
                    <button
                      type="button"
                      onClick={() => {
                        setSearch("");
                        setDoctorFilter(undefined);
                      }}
                      className="underline text-gray-700 hover:text-gray-900"
                    >
                      Limpiar filtros
                    </button>
                  </>
                ) : (
                  "Todavía no hay pacientes registrados en la clínica."
                )}
              </td>
            </tr>
          )}
        </tbody>
      </Table>
    </div>
  );
};

export default PatientsPage;
