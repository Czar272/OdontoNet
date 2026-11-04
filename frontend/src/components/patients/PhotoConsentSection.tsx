import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, ShieldCheck, ShieldOff, ShieldQuestion } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";

import Button from "../basic/Button";
import Input from "../basic/Input";
import LoadingSpinner from "../basic/LoadingSpinner";
import Modal from "../basic/Modal";
import Textarea from "../basic/Textarea";
import { getApiErrorMessage } from "../../services/apiError";
import {
  getPhotoConsent,
  recordPhotoConsent,
} from "../../services/patientImageService";
import type { PhotoConsent, PhotoConsentDTO } from "../../types/patientImage";
import { photoConsentKey, todayLocal } from "./imageUpload";

const dateOnly = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "long",
  timeZone: "UTC",
});
const dateTime = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "medium",
  timeStyle: "short",
});

const formatDate = (value: string) =>
  dateOnly.format(new Date(`${value}T00:00:00Z`));

interface ConsentFormProps {
  initial: PhotoConsentDTO;
  isPending: boolean;
  onSubmit: (data: PhotoConsentDTO) => void;
  onCancel: () => void;
}

function ConsentForm({
  initial,
  isPending,
  onSubmit,
  onCancel,
}: ConsentFormProps) {
  const [form, setForm] = useState(initial);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ ...form, notes: form.notes?.trim() || null });
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <fieldset className="flex flex-col gap-2" disabled={isPending}>
        <legend className="font-medium text-sm mb-1">
          Fotografías clínicas
        </legend>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="granted"
            checked={form.granted}
            onChange={() => setForm({ ...form, granted: true })}
          />
          El paciente autoriza fotografías clínicas
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="granted"
            checked={!form.granted}
            onChange={() =>
              setForm({ ...form, granted: false, research_use: false })
            }
          />
          No autoriza o revoca la autorización
        </label>
      </fieldset>

      <div className="flex flex-col gap-1">
        <label
          className={clsx(
            "flex items-center gap-2",
            !form.granted && "text-gray-400",
          )}
        >
          <input
            type="checkbox"
            checked={form.research_use}
            disabled={!form.granted || isPending}
            onChange={(e) =>
              setForm({ ...form, research_use: e.target.checked })
            }
          />
          Autoriza además el uso en investigación
        </label>
        <p className="text-xs text-gray-500">
          Márcalo solo si el formulario firmado lo autoriza expresamente. Las
          condiciones las fija el protocolo vigente del comité de ética.
        </p>
      </div>

      <Input
        label="Fecha del documento *"
        type="date"
        required
        max={todayLocal()}
        value={form.signed_on}
        disabled={isPending}
        onChange={(e) => setForm({ ...form, signed_on: e.target.value })}
      />
      <Textarea
        label="Notas"
        maxLength={500}
        placeholder="Por ejemplo, dónde está archivado el formulario"
        value={form.notes ?? ""}
        disabled={isPending}
        onChange={(e) => setForm({ ...form, notes: e.target.value })}
      />

      <div className="flex justify-end gap-3">
        <Button variant="secondary" onClick={onCancel} disabled={isPending}>
          Cancelar
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? "Guardando..." : "Guardar consentimiento"}
        </Button>
      </div>
    </form>
  );
}

function ConsentSummary({ consent }: { consent: PhotoConsent }) {
  return (
    <p className="text-sm text-gray-600">
      Registrado por {consent.recorded_by.name} el{" "}
      {dateTime.format(new Date(consent.recorded_at))}
      {consent.notes ? ` · ${consent.notes}` : ""}
    </p>
  );
}

interface PhotoConsentSectionProps {
  patientId: number;
  canManage: boolean;
  isArchived: boolean;
}

/** Consentimiento para fotografías clínicas, versionado (ODON-170). */
export default function PhotoConsentSection({
  patientId,
  canManage,
  isArchived,
}: PhotoConsentSectionProps) {
  const queryClient = useQueryClient();
  const [formInitial, setFormInitial] = useState<PhotoConsentDTO | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: photoConsentKey(patientId),
    queryFn: () => getPhotoConsent(patientId),
  });

  const mutation = useMutation({
    mutationFn: (dto: PhotoConsentDTO) => recordPhotoConsent(patientId, dto),
    onSuccess: (consent) => {
      toast.success(
        consent.granted
          ? "Consentimiento registrado"
          : "Consentimiento revocado",
      );
      setFormInitial(null);
      queryClient.invalidateQueries({ queryKey: photoConsentKey(patientId) });
    },
    onError: (error) => {
      toast.error(
        getApiErrorMessage(error, "No se pudo registrar el consentimiento"),
      );
    },
  });

  if (isLoading) return <LoadingSpinner />;

  const current = data?.current ?? null;
  const history = data?.history ?? [];
  const editable = canManage && !isArchived;

  const open = (granted: boolean) =>
    setFormInitial({
      granted,
      research_use: granted ? (current?.research_use ?? false) : false,
      signed_on: todayLocal(),
      notes: null,
    });

  return (
    <section
      aria-labelledby="photo-consent-title"
      className="flex flex-col gap-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id="photo-consent-title" className="text-lg font-semibold">
          Consentimiento para fotografías
        </h3>
        {editable && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => open(true)}>
              {current?.granted ? "Actualizar" : "Registrar consentimiento"}
            </Button>
            {current?.granted && (
              <Button variant="secondary" onClick={() => open(false)}>
                Revocar
              </Button>
            )}
          </div>
        )}
      </div>

      {current === null ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900"
        >
          <ShieldQuestion size={20} aria-hidden="true" />
          <p>
            Sin consentimiento registrado. No se pueden subir fotografías del
            paciente.
          </p>
        </div>
      ) : current.granted ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-xl border border-green-200 bg-green-50 p-4 text-green-900"
        >
          <ShieldCheck size={20} aria-hidden="true" />
          <div className="flex flex-col gap-1">
            <p>
              Consentimiento vigente, firmado el {formatDate(current.signed_on)}
              .{" "}
              {current.research_use
                ? "Incluye uso en investigación."
                : "No incluye uso en investigación."}
            </p>
            <ConsentSummary consent={current} />
          </div>
        </div>
      ) : (
        <div
          role="status"
          className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-900"
        >
          <ShieldOff size={20} aria-hidden="true" />
          <div className="flex flex-col gap-1">
            <p>
              Consentimiento revocado el {formatDate(current.signed_on)}. No se
              pueden subir fotografías nuevas.
            </p>
            <ConsentSummary consent={current} />
          </div>
        </div>
      )}

      {history.length > 1 && (
        <div>
          <button
            type="button"
            className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
            aria-expanded={showHistory}
            onClick={() => setShowHistory((value) => !value)}
          >
            <History size={16} aria-hidden="true" />
            {showHistory
              ? "Ocultar historial"
              : `Ver historial (${history.length})`}
          </button>
          {showHistory && (
            <ol
              className="mt-2 flex flex-col gap-2"
              aria-label="Historial del consentimiento"
            >
              {history.map((consent) => (
                <li key={consent.id} className="rounded-lg border p-3 text-sm">
                  <p className="font-medium">
                    Versión {consent.version}:{" "}
                    {consent.granted
                      ? `autoriza${consent.research_use ? ", con investigación" : ""}`
                      : "revocado"}{" "}
                    · {formatDate(consent.signed_on)}
                  </p>
                  <ConsentSummary consent={consent} />
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      <Modal
        isOpen={formInitial !== null}
        onClose={() => !mutation.isPending && setFormInitial(null)}
        title={
          formInitial?.granted
            ? "Registrar consentimiento"
            : "Revocar consentimiento"
        }
      >
        {formInitial && (
          <ConsentForm
            key={String(formInitial.granted)}
            initial={formInitial}
            isPending={mutation.isPending}
            onSubmit={(dto) => mutation.mutate(dto)}
            onCancel={() => setFormInitial(null)}
          />
        )}
      </Modal>
    </section>
  );
}
