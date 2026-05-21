import { useQuery } from "@tanstack/react-query";

import { getPatients } from "../../services/patientService";
import type { Patient } from "../../types/patient";
import PatientForm from "../../components/patients/PatientForm";

export default function PatientsPage() {
  const { data: patients, isLoading } = useQuery({
    queryKey: ["patients"],
    queryFn: getPatients,
  });

  if (isLoading) {
    return <p>Loading...</p>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-4xl font-bold">Patients</h1>
      </div>

      <PatientForm />

      <div className="bg-white rounded-2xl shadow overflow-hidden">
        <table className="w-full">
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
        </table>
      </div>
    </div>
  );
}
