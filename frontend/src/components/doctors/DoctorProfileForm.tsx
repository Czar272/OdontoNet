import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import Button from "../basic/Button";
import Input from "../basic/Input";
import Select from "../basic/Select";
import { getApiErrorMessage } from "../../services/apiError";
import { createDoctor, updateDoctor } from "../../services/doctorService";
import type { Doctor } from "../../types/doctor";
import type { User } from "../../types/user";
import {
  buildProfileChanges,
  initialProfileData,
  type DoctorProfileFormData,
} from "./doctorProfileData";

interface DoctorProfileFormProps {
  /** Perfil a editar; sin él, el formulario crea uno nuevo. */
  doctor?: Doctor;
  /** Usuarios con rol doctor o administración sin perfil (solo en alta). */
  candidates?: User[];
  onSuccess?: () => void;
}

const DoctorProfileForm: React.FC<DoctorProfileFormProps> = ({
  doctor,
  candidates = [],
  onSuccess,
}) => {
  const queryClient = useQueryClient();
  const isEdit = Boolean(doctor);

  const [userId, setUserId] = useState<number | "">("");
  const [formData, setFormData] = useState<DoctorProfileFormData>(() =>
    initialProfileData(doctor),
  );

  const mutation = useMutation({
    mutationFn: () => {
      if (doctor) return updateDoctor(doctor.id, buildProfileChanges(doctor, formData));

      return createDoctor({ user_id: Number(userId), ...formData });
    },

    onSuccess: () => {
      toast.success(isEdit ? "Perfil actualizado" : "Perfil creado");
      queryClient.invalidateQueries({ queryKey: ["doctors"] });
      onSuccess?.();
    },

    onError: (error) => {
      toast.error(
        getApiErrorMessage(
          error,
          isEdit ? "No se pudo actualizar el perfil" : "No se pudo crear el perfil",
        ),
      );
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (doctor && Object.keys(buildProfileChanges(doctor, formData)).length === 0) {
      toast("No hay cambios que guardar");
      return;
    }

    mutation.mutate();
  };

  if (!isEdit && candidates.length === 0) {
    return (
      <p className="text-gray-600">
        Todos los usuarios con rol doctor o administración ya tienen perfil. Crea
        primero el usuario en la sección Usuarios.
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {isEdit ? (
          <Input label="Doctor" value={doctor?.user.name ?? ""} disabled readOnly />
        ) : (
          <Select
            name="user_id"
            label="Usuario *"
            value={userId}
            onChange={(e) => setUserId(e.target.value ? Number(e.target.value) : "")}
            required
          >
            <option value="">Selecciona un usuario</option>

            {candidates.map((user) => (
              <option key={user.id} value={user.id}>
                {user.name} ({user.email})
              </option>
            ))}
          </Select>
        )}

        <Input
          name="specialization"
          label="Especialidad"
          placeholder="General"
          value={formData.specialization}
          onChange={handleChange}
          maxLength={100}
        />

        <Input
          name="license_number"
          label="Número de colegiado"
          value={formData.license_number}
          onChange={handleChange}
          maxLength={50}
        />

        <Input
          name="phone"
          type="tel"
          label="Teléfono"
          value={formData.phone}
          onChange={handleChange}
          maxLength={30}
        />
      </div>

      {isEdit && (
        <p className="mt-4 text-xs text-gray-500">
          El nombre, el correo y el estado activo del doctor se gestionan en Usuarios.
        </p>
      )}

      <div className="mt-6 flex justify-end">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Guardando..." : isEdit ? "Guardar cambios" : "Crear perfil"}
        </Button>
      </div>
    </form>
  );
};

export default DoctorProfileForm;
