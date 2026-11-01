import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import Button from "../basic/Button";
import Input from "../basic/Input";
import Select from "../basic/Select";
import { getApiErrorMessage } from "../../services/apiError";
import { getDoctors } from "../../services/doctorService";
import { createPatient } from "../../services/patientService";
import type { CreatePatientDTO } from "../../types/patient";

interface PatientFormProps {
  onSuccess?: () => void;
}

const emptyForm: CreatePatientDTO = {
  first_name: "",
  last_name: "",
  birth_date: "",
  phone: "",
  email: "",
  address: "",
  doctor_id: undefined,
};

const today = new Date().toISOString().slice(0, 10);

const PatientForm: React.FC<PatientFormProps> = ({ onSuccess }) => {
  const queryClient = useQueryClient();

  // Solo doctores activos: el backend rechaza asignar pacientes a inactivos.
  const { data: doctors } = useQuery({
    queryKey: ["doctors", { active: true }],
    queryFn: () => getDoctors({ active: true }),
  });

  const [formData, setFormData] = useState<CreatePatientDTO>(emptyForm);

  const mutation = useMutation({
    mutationFn: createPatient,

    onSuccess: () => {
      toast.success("Paciente creado");
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      setFormData(emptyForm);
      onSuccess?.();
    },

    onError: (error) => {
      toast.error(getApiErrorMessage(error, "No se pudo crear el paciente"));
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleDoctorChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData({
      ...formData,
      doctor_id: e.target.value ? Number(e.target.value) : undefined,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(formData);
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          name="first_name"
          label="Nombres *"
          value={formData.first_name}
          onChange={handleChange}
          required
        />

        <Input
          name="last_name"
          label="Apellidos *"
          value={formData.last_name}
          onChange={handleChange}
          required
        />

        <Input
          name="birth_date"
          type="date"
          label="Fecha de nacimiento"
          max={today}
          value={formData.birth_date}
          onChange={handleChange}
        />

        <Input
          name="phone"
          type="tel"
          label="Teléfono"
          value={formData.phone}
          onChange={handleChange}
        />

        <Input
          name="email"
          type="email"
          label="Correo electrónico"
          value={formData.email}
          onChange={handleChange}
        />

        <Input
          name="address"
          label="Dirección"
          value={formData.address}
          onChange={handleChange}
        />

        <Select
          name="doctor_id"
          label="Doctor asignado"
          value={formData.doctor_id ?? ""}
          onChange={handleDoctorChange}
        >
          <option value="">Sin asignar</option>

          {doctors?.map((doctor) => (
            <option key={doctor.id} value={doctor.id}>
              {doctor.user.name}
            </option>
          ))}
        </Select>
      </div>

      <div className="mt-6 flex justify-end">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Guardando..." : "Guardar paciente"}
        </Button>
      </div>
    </form>
  );
};

export default PatientForm;
