import { useQuery } from "@tanstack/react-query";
import { getPatients } from "../../services/patientService";
import type { Patient } from "../../types/patient";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import PageHeader from "../../components/basic/PageHeader";
import Table from "../../components/basic/Table";
import PatientForm from "../../components/patients/PatientForm";
import { useMemo, useState } from "react";
import Button from "../../components/basic/Button";
import Modal from "../../components/basic/Modal";
import Input from "../../components/basic/Input";

const PatientsPage: React.FC = () => {
  const { data: patients, isLoading } = useQuery({
    queryKey: ["patients"],
    queryFn: getPatients,
  });

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [doctorFilter, setDoctorFilter] = useState<number | undefined>();

  const doctors = useMemo(() => {
    if (!patients) return [];

    return [
      ...new Map(
        patients
          .filter((p: Patient) => p.doctor)

          .map((p: Patient) => [p.doctor!.id, p.doctor]),
      ).values(),
    ];
  }, [patients]);

  const filteredPatients = useMemo(() => {
    if (!patients) return [];

    return patients.filter((p: Patient) => {
      const fullName = `${p.first_name} ${p.last_name}`.toLowerCase();
      const matchesSearch = fullName.includes(search.toLowerCase());
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
        title="Patients"
        description="Manage clinic patients"
        action={
          <Button onClick={() => setIsModalOpen(true)}>New Patient</Button>
        }
      />

      <div className="flex gap-4 mb-6 ">
        <div className="flex-1">
          <Input
            placeholder="Search patients..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <select
          value={doctorFilter || ""}
          onChange={(e) =>
            setDoctorFilter(e.target.value ? Number(e.target.value) : undefined)
          }
          className="border rounded-xl px-4 py-3 bg-white"
        >
          <option value="">All Doctors</option>

          {doctors.map((doctor, i) => (
            <option key={i} value={doctor ? doctor.id : 0}>
              {doctor ? doctor.user.name : "No doctor"}
            </option>
          ))}
        </select>
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create Patient"
      >
        <PatientForm />
      </Modal>

      <Table>
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left p-4">Name</th>

            <th className="text-left p-4">Email</th>

            <th className="text-left p-4">Phone</th>

            <th className="text-left p-4">Doctor</th>
          </tr>
        </thead>

        <tbody>
          {filteredPatients?.map((patient: Patient) => (
            <tr key={patient.id} className="border-t">
              <td className="p-4">
                {patient.first_name} {patient.last_name}
              </td>

              <td className="p-4">{patient.email}</td>

              <td className="p-4">{patient.phone}</td>

              <td className="p-4">{patient.doctor?.user.name}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
};

export default PatientsPage;
