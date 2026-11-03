import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  Archive,
  ArchiveRestore,
  ArrowLeft,
  ClipboardList,
  Lock,
  Pencil,
  SearchX,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import toast from "react-hot-toast";

import Button from "../../components/basic/Button";
import Card from "../../components/basic/Card";
import ConfirmDialog from "../../components/basic/ConfirmDialog";
import Input from "../../components/basic/Input";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import Select from "../../components/basic/Select";
import ClinicalVisitsCard from "../../components/patients/ClinicalVisitsCard";
import MedicalHistoryCard from "../../components/patients/MedicalHistoryCard";
import { usePermission } from "../../hooks/usePermission";
import { getApiErrorMessage } from "../../services/apiError";
import { getDoctors } from "../../services/doctorService";
import {
  archivePatient,
  getPatient,
  reactivatePatient,
  updatePatient,
} from "../../services/patientService";
import type { Patient } from "../../types/patient";
import {
  ageFrom,
  buildPatientChanges,
  initialPatientData,
  type PatientFormData,
} from "./patientFormData";

const today = new Date().toISOString().slice(0, 10);

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center text-center py-20 gap-4">
      <SearchX size={48} className="text-gray-400" aria-hidden="true" />
      <h1 className="text-3xl font-bold">Paciente no encontrado</h1>
      <p className="text-gray-500 max-w-md">
        El paciente no existe o no pertenece a tu clínica.
      </p>
      <Link
        to="/patients"
        className="px-5 py-3 rounded-xl font-medium bg-gray-900 text-white hover:bg-gray-800 transition"
      >
        Volver a pacientes
      </Link>
    </div>
  );
}

interface PatientFormProps {
  patient: Patient;
  canEdit: boolean;
  isArchived: boolean;
}

/** Datos generales con edición en dos pasos, igual que en Clínica. */
function PatientDataForm({
  patient,
  canEdit: hasEditPermission,
  isArchived,
}: PatientFormProps) {
  // Un paciente archivado se reactiva antes de editarse (el backend responde 409).
  const canEdit = hasEditPermission && !isArchived;
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<PatientFormData>(() =>
    initialPatientData(patient),
  );

  // Activos para asignar; el doctor actual se conserva aunque esté inactivo.
  const { data: activeDoctors } = useQuery({
    queryKey: ["doctors", { active: true }],
    queryFn: () => getDoctors({ active: true }),
    enabled: canEdit,
  });
  const doctorOptions = [...(activeDoctors ?? [])];
  if (
    patient.doctor &&
    !doctorOptions.some((d) => d.id === patient.doctor?.id)
  ) {
    doctorOptions.push(patient.doctor);
  }

  const mutation = useMutation({
    mutationFn: () =>
      updatePatient(patient.id, buildPatientChanges(patient, formData)),

    onSuccess: (updated) => {
      toast.success("Paciente actualizado");
      setIsEditing(false);
      queryClient.setQueryData(["patients", patient.id], updated);
      queryClient.invalidateQueries({ queryKey: ["patients", "list"] });
    },

    onError: (error) => {
      toast.error(
        getApiErrorMessage(error, "No se pudo actualizar el paciente"),
      );
    },
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleCancel = () => {
    setFormData(initialPatientData(patient));
    setIsEditing(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (Object.keys(buildPatientChanges(patient, formData)).length === 0) {
      toast("No hay cambios que guardar");
      return;
    }

    mutation.mutate();
  };

  const age = ageFrom(patient.birth_date);

  return (
    <form onSubmit={handleSubmit}>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Datos generales</h2>

        {canEdit && !isEditing && (
          <Button variant="secondary" onClick={() => setIsEditing(true)}>
            <span className="flex items-center gap-2">
              <Pencil size={16} /> Editar datos
            </span>
          </Button>
        )}

        {!isEditing && !canEdit && (
          <span className="flex items-center gap-2 text-sm text-gray-500">
            <Lock size={16} />{" "}
            {isArchived ? "Archivado: solo lectura" : "Solo lectura"}
          </span>
        )}
      </div>

      <fieldset
        disabled={!isEditing || mutation.isPending}
        className="grid grid-cols-1 sm:grid-cols-2 gap-4"
      >
        <Input
          name="first_name"
          label="Nombres *"
          value={formData.first_name}
          onChange={handleChange}
          maxLength={100}
          required
        />
        <Input
          name="last_name"
          label="Apellidos *"
          value={formData.last_name}
          onChange={handleChange}
          maxLength={100}
          required
        />

        <div className="flex flex-col gap-1">
          <Input
            name="birth_date"
            type="date"
            label="Fecha de nacimiento"
            max={today}
            value={formData.birth_date}
            onChange={handleChange}
          />
          {age !== null && !isEditing && (
            <p className="text-xs text-gray-500">{age} años</p>
          )}
        </div>

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

        <Select
          name="doctor_id"
          label="Doctor asignado"
          value={formData.doctor_id}
          onChange={handleChange}
        >
          <option value="">Sin asignar</option>
          {(isEditing
            ? doctorOptions
            : patient.doctor
              ? [patient.doctor]
              : []
          ).map((doctor) => (
            <option key={doctor.id} value={doctor.id}>
              {doctor.user.name}
              {doctor.user.is_active ? "" : " (inactivo)"}
            </option>
          ))}
        </Select>
      </fieldset>

      {isEditing && (
        <div className="mt-6 flex justify-end gap-3">
          <Button
            variant="secondary"
            onClick={handleCancel}
            disabled={mutation.isPending}
          >
            Cancelar
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Guardando..." : "Guardar cambios"}
          </Button>
        </div>
      )}
    </form>
  );
}

const dateFormat = new Intl.DateTimeFormat("es-GT", { dateStyle: "long" });

/** Archivar o reactivar con confirmación (ODON-122). No borra datos. */
function ArchiveControls({ patient }: { patient: Patient }) {
  const queryClient = useQueryClient();
  const [isConfirming, setIsConfirming] = useState(false);
  const isArchived = Boolean(patient.archived_at);

  const mutation = useMutation({
    mutationFn: () =>
      isArchived ? reactivatePatient(patient.id) : archivePatient(patient.id),

    onSuccess: (updated) => {
      toast.success(
        updated.archived_at ? "Paciente archivado" : "Paciente reactivado",
      );
      setIsConfirming(false);
      queryClient.setQueryData(["patients", patient.id], updated);
      queryClient.invalidateQueries({ queryKey: ["patients", "list"] });
    },

    onError: (error) => {
      toast.error(
        getApiErrorMessage(error, "No se pudo cambiar el estado del paciente"),
      );
    },
  });

  const name = `${patient.first_name} ${patient.last_name}`;

  return (
    <>
      <Button
        variant={isArchived ? "primary" : "secondary"}
        onClick={() => setIsConfirming(true)}
      >
        <span className="flex items-center gap-2">
          {isArchived ? <ArchiveRestore size={16} /> : <Archive size={16} />}
          {isArchived ? "Reactivar paciente" : "Archivar paciente"}
        </span>
      </Button>

      <ConfirmDialog
        isOpen={isConfirming}
        title={isArchived ? "Reactivar paciente" : "Archivar paciente"}
        message={
          isArchived ? (
            <p>
              <strong>{name}</strong> volverá al listado de pacientes activos y
              podrá editarse de nuevo.
            </p>
          ) : (
            <p>
              <strong>{name}</strong> dejará de aparecer en el listado de
              pacientes activos. No se borra ningún dato: su ficha e historial
              se conservan y puedes reactivarlo cuando lo necesites.
            </p>
          )
        }
        confirmLabel={isArchived ? "Reactivar" : "Archivar"}
        variant={isArchived ? "primary" : "danger"}
        isPending={mutation.isPending}
        onConfirm={() => mutation.mutate()}
        onCancel={() => setIsConfirming(false)}
      />
    </>
  );
}

/** Ficha del paciente (ODON-114): datos generales y acceso al historial clínico. */
export default function PatientDetailPage() {
  const { patientId } = useParams();
  const id = Number(patientId);
  const validId = Number.isInteger(id) && id > 0;
  const canEdit = usePermission("patients:edit");
  const canArchive = usePermission("patients:archive");
  const canViewHistory = usePermission("medical_history:view");
  const canEditHistory = usePermission("medical_history:edit");
  const canViewVisits = usePermission("visits:view");
  const canCreateVisits = usePermission("visits:create");

  const {
    data: patient,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["patients", id],
    queryFn: () => getPatient(id),
    enabled: validId,
  });

  if (
    !validId ||
    (axios.isAxiosError(error) && error.response?.status === 404)
  ) {
    return <NotFound />;
  }

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!patient) {
    return <p className="text-gray-500">No se pudo cargar el paciente.</p>;
  }

  return (
    <div>
      <Link
        to="/patients"
        className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-4"
      >
        <ArrowLeft size={16} /> Pacientes
      </Link>

      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-4xl font-bold">
            {patient.first_name} {patient.last_name}
          </h1>
          <p className="text-gray-500 mt-2">
            {patient.doctor
              ? `Doctor asignado: ${patient.doctor.user.name}`
              : "Sin doctor asignado"}
          </p>
        </div>

        {canArchive && <ArchiveControls patient={patient} />}
      </div>

      {patient.archived_at && (
        <div
          role="status"
          className="mb-6 flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900"
        >
          <Archive size={20} aria-hidden="true" />
          <p>
            Paciente archivado el{" "}
            {dateFormat.format(new Date(patient.archived_at))}. Sus datos e
            historial se conservan; reactívalo para editarlo.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <Card className="xl:col-span-2">
          <PatientDataForm
            key={JSON.stringify(patient)}
            patient={patient}
            canEdit={canEdit}
            isArchived={Boolean(patient.archived_at)}
          />
        </Card>

        <Card>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <ClipboardList size={20} /> Historial clínico
          </h2>
          <p className="text-gray-500 text-sm">
            Los planes de tratamiento se mostrarán aquí cuando se habiliten en
            el expediente clínico.
          </p>
        </Card>
      </div>

      {canViewHistory && (
        <div className="mt-6">
          <MedicalHistoryCard
            patientId={patient.id}
            canEdit={canEditHistory}
            isArchived={Boolean(patient.archived_at)}
          />
        </div>
      )}

      {canViewVisits && (
        <div className="mt-6">
          <ClinicalVisitsCard
            patientId={patient.id}
            canCreate={canCreateVisits}
            isArchived={Boolean(patient.archived_at)}
          />
        </div>
      )}
    </div>
  );
}
