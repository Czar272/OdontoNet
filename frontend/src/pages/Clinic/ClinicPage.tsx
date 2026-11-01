import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import Button from "../../components/basic/Button";
import Card from "../../components/basic/Card";
import Input from "../../components/basic/Input";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import PageHeader from "../../components/basic/PageHeader";
import { useAuth } from "../../context/AuthContext";
import { usePermission } from "../../hooks/usePermission";
import { getApiErrorMessage } from "../../services/apiError";
import { getClinic, updateClinic } from "../../services/clinicService";
import type { Clinic } from "../../types/clinic";
import { buildClinicChanges, initialClinicData, type ClinicFormData } from "./clinicFormData";

interface ClinicFormProps {
  clinic: Clinic;
  canManage: boolean;
}

const ClinicForm: React.FC<ClinicFormProps> = ({ clinic, canManage }) => {
  const queryClient = useQueryClient();
  const { refreshUser } = useAuth();
  const [formData, setFormData] = useState<ClinicFormData>(() => initialClinicData(clinic));

  const mutation = useMutation({
    mutationFn: () => updateClinic(buildClinicChanges(clinic, formData)),

    onSuccess: async (updated) => {
      toast.success("Datos de la clínica actualizados");
      queryClient.setQueryData(["clinic"], updated);
      // El nombre de la clínica aparece en el menú lateral (viene de /auth/me).
      await refreshUser();
    },

    onError: (error) => {
      toast.error(getApiErrorMessage(error, "No se pudieron guardar los cambios"));
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (Object.keys(buildClinicChanges(clinic, formData)).length === 0) {
      toast("No hay cambios que guardar");
      return;
    }

    mutation.mutate();
  };

  return (
    <form onSubmit={handleSubmit}>
      <fieldset disabled={!canManage} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          name="name"
          label="Nombre de la clínica *"
          value={formData.name}
          onChange={handleChange}
          maxLength={120}
          required
        />

        <Input
          name="phone"
          type="tel"
          label="Teléfono"
          value={formData.phone}
          onChange={handleChange}
          maxLength={30}
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
          maxLength={255}
        />
      </fieldset>

      {canManage ? (
        <div className="mt-6 flex justify-end">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Guardando..." : "Guardar cambios"}
          </Button>
        </div>
      ) : (
        <p className="mt-6 text-sm text-gray-500">
          Solo administración puede modificar los datos de la clínica.
        </p>
      )}
    </form>
  );
};

/** Datos de la clínica de la sesión (ODON-74). Todos consultan; administración edita. */
const ClinicPage: React.FC = () => {
  const canManage = usePermission("clinic:manage");
  const { data: clinic, isLoading, isError } = useQuery({
    queryKey: ["clinic"],
    queryFn: getClinic,
  });

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div>
      <PageHeader title="Clínica" description="Datos generales de tu clínica" />

      <Card className="max-w-3xl">
        {isError || !clinic ? (
          <p className="text-gray-500">No se pudieron cargar los datos de la clínica.</p>
        ) : (
          // key: reinicia el formulario si los datos cambian desde otra parte.
          <ClinicForm key={`${clinic.id}-${clinic.name}`} clinic={clinic} canManage={canManage} />
        )}
      </Card>
    </div>
  );
};

export default ClinicPage;
