import { useQuery } from "@tanstack/react-query";
import { getPatients } from "../../services/patientService";
import type { Patient } from "../../types/patient";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import PageHeader from "../../components/basic/PageHeader";
import Table from "../../components/basic/Table";
import PatientForm from "../../components/patients/PatientForm";

export default function PatientsPage() {
  const { data: patients, isLoading } = useQuery({
    queryKey: ["patients"],
    queryFn: getPatients,
  });

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div>
      <PageHeader title="Patients" description="Manage clinic patients" />

      <PatientForm />

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
}
