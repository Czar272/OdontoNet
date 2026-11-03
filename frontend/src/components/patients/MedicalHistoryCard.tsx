import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { History, HeartPulse, Lock, Pencil } from "lucide-react";
import toast from "react-hot-toast";

import Button from "../basic/Button";
import Card from "../basic/Card";
import Input from "../basic/Input";
import LoadingSpinner from "../basic/LoadingSpinner";
import Select from "../basic/Select";
import Textarea from "../basic/Textarea";
import { getApiErrorMessage } from "../../services/apiError";
import {
  getMedicalHistory,
  getMedicalHistoryVersion,
  getMedicalHistoryVersions,
  saveMedicalHistory,
} from "../../services/medicalHistoryService";
import type { MedicalHistory, SmokingStatus } from "../../types/medicalHistory";
import {
  CONDITIONS,
  SMOKING_LABELS,
  TRI_STATE_OPTIONS,
  buildSaveMedicalHistory,
  initialMedicalHistoryForm,
  isUnchanged,
  type MedicalHistoryFormData,
  type TextField,
  type TriState,
} from "./medicalHistoryForm";
import { timelineKey } from "./timelineEvents";

const dateTimeFormat = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "long",
  timeStyle: "short",
});

function versionLabel(history: {
  version: number;
  created_at: string;
  created_by: { name: string };
}) {
  return `Versión ${history.version} · ${dateTimeFormat.format(new Date(history.created_at))} · ${history.created_by.name}`;
}

interface MedicalHistoryCardProps {
  patientId: number;
  canEdit: boolean;
  isArchived: boolean;
}

/**
 * Historia médica y odontológica (ODON-150). Cada guardado crea una versión
 * nueva; las anteriores se consultan en solo lectura. Edición en dos pasos.
 */
export default function MedicalHistoryCard({
  patientId,
  canEdit: hasEditPermission,
  isArchived,
}: MedicalHistoryCardProps) {
  const canEdit = hasEditPermission && !isArchived;
  const queryClient = useQueryClient();
  const historyKey = ["patients", patientId, "medical-history"];

  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState<MedicalHistoryFormData>(() =>
    initialMedicalHistoryForm(null),
  );
  // null = versión vigente.
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);

  const { data: current, isLoading } = useQuery({
    queryKey: historyKey,
    queryFn: () => getMedicalHistory(patientId),
  });

  const { data: versions } = useQuery({
    queryKey: [...historyKey, "versions"],
    queryFn: () => getMedicalHistoryVersions(patientId),
    enabled: Boolean(current),
  });

  const viewingOld =
    selectedVersion !== null && selectedVersion !== current?.version;

  const { data: oldVersion } = useQuery({
    queryKey: [...historyKey, "versions", selectedVersion],
    queryFn: () =>
      getMedicalHistoryVersion(patientId, selectedVersion as number),
    enabled: viewingOld,
  });

  const displayed: MedicalHistory | null = viewingOld
    ? (oldVersion ?? null)
    : (current ?? null);
  const shownForm = isEditing ? form : initialMedicalHistoryForm(displayed);

  const mutation = useMutation({
    mutationFn: () =>
      saveMedicalHistory(
        patientId,
        buildSaveMedicalHistory(form, current ?? null),
      ),

    onSuccess: (saved) => {
      toast.success(`Historia médica guardada (versión ${saved.version})`);
      queryClient.setQueryData(historyKey, saved);
      queryClient.invalidateQueries({ queryKey: [...historyKey, "versions"] });
      queryClient.invalidateQueries({ queryKey: timelineKey(patientId) });
      setSelectedVersion(null);
      setIsEditing(false);
    },

    onError: (error) => {
      toast.error(
        getApiErrorMessage(error, "No se pudo guardar la historia médica"),
      );
      // Otra persona guardó antes: se recarga la vigente y se conserva lo escrito.
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        queryClient.invalidateQueries({ queryKey: historyKey });
      }
    },
  });

  const startEditing = () => {
    setForm(initialMedicalHistoryForm(current ?? null));
    setSelectedVersion(null);
    setIsEditing(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (current && isUnchanged(form, current)) {
      toast("No hay cambios que guardar");
      return;
    }
    mutation.mutate();
  };

  const setField = (field: TextField, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const setCondition = (
    key: keyof MedicalHistoryFormData["conditions"],
    part: "present" | "detail",
    value: string,
  ) =>
    setForm((prev) => ({
      ...prev,
      conditions: {
        ...prev.conditions,
        [key]: { ...prev.conditions[key], [part]: value },
      },
    }));

  const text = (field: TextField) => ({
    value: shownForm[field],
    onChange: (
      e: React.ChangeEvent<
        HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
      >,
    ) => setField(field, e.target.value),
  });

  const triSelect = (field: TextField, label: string) => (
    <Select label={label} {...text(field)}>
      {TRI_STATE_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </Select>
  );

  if (isLoading) {
    return (
      <Card>
        <LoadingSpinner />
      </Card>
    );
  }

  const hasHistory = Boolean(current);

  return (
    <Card>
      <form onSubmit={handleSubmit} aria-label="Historia médica y odontológica">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <HeartPulse size={20} /> Historia médica y odontológica
            </h2>
            {displayed && !isEditing && (
              <p
                className="text-sm text-gray-500 mt-1"
                data-testid="history-version"
              >
                {versionLabel(displayed)}
              </p>
            )}
          </div>

          <div className="flex items-center gap-3">
            {!isEditing && versions && versions.length > 1 && (
              <Select
                aria-label="Versión"
                value={selectedVersion ?? current?.version ?? ""}
                onChange={(e) => setSelectedVersion(Number(e.target.value))}
              >
                {versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    {v.version === current?.version
                      ? `${versionLabel(v)} (vigente)`
                      : versionLabel(v)}
                  </option>
                ))}
              </Select>
            )}

            {canEdit && !isEditing && (
              <Button variant="secondary" onClick={startEditing}>
                <span className="flex items-center gap-2">
                  <Pencil size={16} />{" "}
                  {hasHistory ? "Editar historia" : "Registrar historia"}
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
        </div>

        {viewingOld && !isEditing && (
          <div
            role="status"
            className="mb-6 flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 text-blue-900"
          >
            <History size={20} aria-hidden="true" />
            <p>
              Estás viendo una versión anterior. La vigente es la versión{" "}
              {current?.version}.
            </p>
          </div>
        )}

        {!hasHistory && !isEditing ? (
          <p className="text-gray-500 text-sm">
            Este paciente aún no tiene historia médica registrada.
          </p>
        ) : (
          <fieldset
            disabled={!isEditing || mutation.isPending}
            className="flex flex-col gap-8"
          >
            <section className="flex flex-col gap-4">
              <h3 className="font-semibold text-gray-700">
                Antecedentes médicos
              </h3>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {CONDITIONS.map(({ key, label }) => (
                  <div
                    key={key}
                    className="grid grid-cols-[minmax(0,10rem)_1fr] gap-2 items-end"
                  >
                    <Select
                      label={label}
                      value={shownForm.conditions[key].present}
                      onChange={(e) =>
                        setCondition(key, "present", e.target.value as TriState)
                      }
                    >
                      {TRI_STATE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </Select>
                    <Input
                      aria-label={`Detalle: ${label}`}
                      placeholder="Detalle"
                      maxLength={500}
                      value={shownForm.conditions[key].detail}
                      onChange={(e) =>
                        setCondition(key, "detail", e.target.value)
                      }
                    />
                  </div>
                ))}
              </div>

              <Textarea
                label="Otras enfermedades"
                maxLength={2000}
                {...text("other_conditions")}
              />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Textarea
                  label="Alergias"
                  maxLength={2000}
                  {...text("allergies")}
                />
                <Textarea
                  label="Medicamentos actuales"
                  maxLength={2000}
                  {...text("current_medications")}
                />
              </div>
            </section>

            <section className="flex flex-col gap-4">
              <h3 className="font-semibold text-gray-700">Hábitos</h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <Select label="Tabaquismo" {...text("smoking_status")}>
                  <option value="">Sin dato</option>
                  {(Object.keys(SMOKING_LABELS) as SmokingStatus[]).map(
                    (status) => (
                      <option key={status} value={status}>
                        {SMOKING_LABELS[status]}
                      </option>
                    ),
                  )}
                </Select>

                {shownForm.smoking_status === "current" && (
                  <Input
                    label="Cigarrillos al día"
                    type="number"
                    min={1}
                    max={200}
                    {...text("cigarettes_per_day")}
                  />
                )}

                {triSelect("alcohol", "Alcohol")}
                <Input
                  label="Detalle de alcohol"
                  maxLength={500}
                  {...text("alcohol_detail")}
                />
                {triSelect("bruxism", "Bruxismo")}
              </div>
            </section>

            <section className="flex flex-col gap-4">
              <h3 className="font-semibold text-gray-700">
                Antecedentes odontológicos
              </h3>

              <Textarea
                label="Motivo de consulta"
                maxLength={2000}
                {...text("chief_complaint")}
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <Input
                  label="Última visita al dentista"
                  placeholder="Ej. hace 2 años"
                  maxLength={80}
                  {...text("last_dental_visit")}
                />
                <Input
                  label="Cepillado (veces al día)"
                  type="number"
                  min={0}
                  max={10}
                  {...text("brushing_per_day")}
                />
                {triSelect("uses_floss", "Usa hilo dental")}
                {triSelect("gum_bleeding", "Sangrado de encías")}
              </div>

              <Textarea
                label="Tratamientos previos"
                maxLength={2000}
                {...text("previous_treatments")}
              />
            </section>

            <Textarea
              label="Observaciones"
              rows={3}
              maxLength={2000}
              {...text("notes")}
            />
          </fieldset>
        )}

        {isEditing && (
          <div className="mt-6 flex justify-end gap-3">
            <Button
              variant="secondary"
              onClick={() => setIsEditing(false)}
              disabled={mutation.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Guardando..." : "Guardar historia"}
            </Button>
          </div>
        )}
      </form>
    </Card>
  );
}
