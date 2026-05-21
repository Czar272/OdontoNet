import { useQuery } from "@tanstack/react-query";
import { getPatients } from "../../services/patientService";
import type { Patient } from "../../types/patient";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import PageHeader from "../../components/basic/PageHeader";
import Table from "../../components/basic/Table";
import PatientForm from "../../components/patients/PatientForm";
import { useState } from "react";
import Button from "../../components/basic/Button";
import Modal from "../../components/basic/Modal";

const PatientsPage: React.FC = () => {
  const { data: patients, isLoading } = useQuery({
    queryKey: ["patients"],
    queryFn: getPatients,
  });

  const [isModalOpen, setIsModalOpen] = useState(false);

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
          </tr>
        </thead>

        <tbody>
          {patients?.map((patient: Patient) => (
            <tr key={patient.id} className="border-t">
              <td className="p-4">
                {patient.first_name} {patient.last_name}
              </td>

              <td className="p-4">{patient.email}</td>

              <td className="p-4">{patient.phone}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
};

export default PatientsPage;
