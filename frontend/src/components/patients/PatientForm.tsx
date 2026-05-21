import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createPatient } from "../../services/patientService";
import type { CreatePatientDTO } from "../../types/patient";
import toast from "react-hot-toast";

export default function PatientForm() {
  const queryClient = useQueryClient();

  const [formData, setFormData] = useState<CreatePatientDTO>({
    first_name: "",
    last_name: "",
    birth_date: "",
    phone: "",
    email: "",
    address: "",
  });

  const mutation = useMutation({
    mutationFn: createPatient,

    onSuccess: () => {
      toast.success("Patient Created");
      queryClient.invalidateQueries({
        queryKey: ["patients"],
      });

      setFormData({
        first_name: "",
        last_name: "",
        birth_date: "",
        phone: "",
        email: "",
        address: "",
      });
    },

    onError: () => {
      toast.error("Error creando el paciente");
    },
  });

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    mutation.mutate(formData);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white p-6 rounded-2xl shadow mb-8"
    >
      <h2 className="text-2xl font-bold mb-6">New Patient</h2>

      <div className="grid grid-cols-2 gap-4">
        <input
          name="first_name"
          placeholder="First Name"
          value={formData.first_name}
          onChange={handleChange}
          className="border p-3 rounded-lg"
          required
        />

        <input
          name="last_name"
          placeholder="Last Name"
          value={formData.last_name}
          onChange={handleChange}
          className="border p-3 rounded-lg"
          required
        />

        <input
          name="birth_date"
          type="date"
          value={formData.birth_date}
          onChange={handleChange}
          className="border p-3 rounded-lg"
        />

        <input
          name="phone"
          placeholder="Phone"
          value={formData.phone}
          onChange={handleChange}
          className="border p-3 rounded-lg"
        />

        <input
          name="email"
          placeholder="Email"
          value={formData.email}
          onChange={handleChange}
          className="border p-3 rounded-lg"
        />

        <input
          name="address"
          placeholder="Address"
          value={formData.address}
          onChange={handleChange}
          className="border p-3 rounded-lg"
        />
      </div>

      <button
        type="submit"
        className="mt-6 bg-gray-900 text-white px-6 py-3 rounded-lg hover:bg-gray-800"
      >
        Create Patient
      </button>
    </form>
  );
}
