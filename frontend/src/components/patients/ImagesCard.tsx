import { useId, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Lock } from "lucide-react";
import toast from "react-hot-toast";

import Button from "../basic/Button";
import Card from "../basic/Card";
import Select from "../basic/Select";
import { getApiErrorMessage } from "../../services/apiError";
import { getVisits } from "../../services/clinicalVisitService";
import {
  getPhotoConsent,
  uploadPatientImage,
} from "../../services/patientImageService";
import ImageGallery from "./ImageGallery";
import PhotoConsentSection from "./PhotoConsentSection";
import ToothChart from "./ToothChart";
import { timelineKey } from "./timelineEvents";
import {
  ACCEPTED_IMAGE_EXTENSIONS,
  ACCEPTED_IMAGE_TYPES,
  MAX_IMAGE_MB,
  formatBytes,
  patientImagesKey,
  photoConsentKey,
  readAsDataUrl,
  validateImageFile,
} from "./imageUpload";

const dateTime = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "medium",
  timeStyle: "short",
});

function UploadForm({ patientId }: { patientId: number }) {
  const queryClient = useQueryClient();
  const fileInputId = useId();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [visitId, setVisitId] = useState("");
  const [tooth, setTooth] = useState<number | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  const { data: allVisits = [] } = useQuery({
    queryKey: ["patients", patientId, "visits"],
    queryFn: () => getVisits(patientId),
  });
  const visits = allVisits.filter((visit) => !visit.voided_at);

  const reset = () => {
    setFile(null);
    setPreview(null);
    setTooth(null);
    setVisitId("");
    setProgress(null);
    if (fileInput.current) fileInput.current.value = "";
  };

  const mutation = useMutation({
    mutationFn: (selected: File) =>
      uploadPatientImage(
        patientId,
        {
          file: selected,
          clinical_visit_id: visitId ? Number(visitId) : null,
          tooth,
        },
        setProgress,
      ),
    onSuccess: () => {
      toast.success("Imagen subida");
      reset();
      queryClient.invalidateQueries({ queryKey: patientImagesKey(patientId) });
      queryClient.invalidateQueries({ queryKey: timelineKey(patientId) });
    },
    onError: (error) => {
      setProgress(null);
      toast.error(getApiErrorMessage(error, "No se pudo subir la imagen"));
      // El consentimiento pudo cambiar en otra sesión.
      queryClient.invalidateQueries({ queryKey: photoConsentKey(patientId) });
    },
  });

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    const error = selected ? validateImageFile(selected) : null;
    const accepted = error ? null : selected;
    setFileError(error);
    setFile(accepted);
    setPreview(null);
    if (accepted) {
      readAsDataUrl(accepted)
        .then((url) => {
          // Si mientras tanto se eligió otro archivo, se descarta.
          if (fileInput.current?.files?.[0] === accepted) setPreview(url);
        })
        .catch(() => setPreview(null));
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setFileError("Elige una fotografía.");
      return;
    }
    mutation.mutate(file);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <fieldset disabled={mutation.isPending} className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <label htmlFor={fileInputId} className="font-medium text-sm">
            Fotografía *
          </label>
          <input
            id={fileInputId}
            ref={fileInput}
            type="file"
            accept={[
              ...ACCEPTED_IMAGE_TYPES,
              ...ACCEPTED_IMAGE_EXTENSIONS,
            ].join(",")}
            onChange={handleFile}
            aria-invalid={fileError !== null}
            aria-describedby={`${fileInputId}-help`}
            className="text-sm"
          />
          <p id={`${fileInputId}-help`} className="text-xs text-gray-500">
            JPEG, PNG o WebP de hasta {MAX_IMAGE_MB} MB. Al guardarla se quitan
            los metadatos (ubicación, dispositivo).
          </p>
          {fileError && (
            <p role="alert" className="text-sm text-red-600">
              {fileError}
            </p>
          )}
          {preview && file && (
            <div className="flex items-center gap-3">
              <img
                src={preview}
                alt="Vista previa de la fotografía elegida"
                className="h-24 w-24 rounded-lg object-cover"
              />
              <span className="text-sm text-gray-600">
                {file.name} · {formatBytes(file.size)}
              </span>
            </div>
          )}
        </div>

        <Select
          label="Consulta (opcional)"
          value={visitId}
          onChange={(e) => setVisitId(e.target.value)}
        >
          <option value="">Sin consulta</option>
          {visits.map((visit) => (
            <option key={visit.id} value={visit.id}>
              {dateTime.format(new Date(visit.visit_at))} · {visit.reason}
            </option>
          ))}
        </Select>

        <ToothChart
          value={tooth}
          onChange={setTooth}
          hint={
            tooth
              ? `Pieza ${tooth}. Tócala de nuevo para quitarla.`
              : "Pieza (opcional): toca una pieza para asociarla a la foto."
          }
        />
      </fieldset>

      {progress !== null && (
        <div className="flex flex-col gap-1">
          <div
            role="progressbar"
            aria-label="Progreso de la subida"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
            className="h-2 w-full overflow-hidden rounded-full bg-gray-200"
          >
            <div
              className="h-full bg-gray-900 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-gray-500">
            {progress < 100
              ? `Subiendo… ${progress} %`
              : "Procesando la imagen…"}
          </p>
        </div>
      )}

      <div className="flex justify-end">
        <Button type="submit" disabled={mutation.isPending || !file}>
          <span className="flex items-center gap-2">
            <ImagePlus size={16} />
            {mutation.isPending ? "Subiendo..." : "Subir imagen"}
          </span>
        </Button>
      </div>
    </form>
  );
}

interface ImagesCardProps {
  patientId: number;
  canUpload: boolean;
  isArchived: boolean;
}

/** Imágenes clínicas del paciente: consentimiento, subida (ODON-170) y galería (ODON-174). */
export default function ImagesCard({
  patientId,
  canUpload,
  isArchived,
}: ImagesCardProps) {
  const { data: consent } = useQuery({
    queryKey: photoConsentKey(patientId),
    queryFn: () => getPhotoConsent(patientId),
  });
  const hasConsent = consent?.current?.granted === true;

  return (
    <Card>
      <div className="flex flex-col gap-6">
        <h2 className="text-xl font-semibold">Imágenes clínicas</h2>

        <PhotoConsentSection
          patientId={patientId}
          canManage={canUpload}
          isArchived={isArchived}
        />

        <section
          aria-labelledby="image-upload-title"
          className="flex flex-col gap-3"
        >
          <h3 id="image-upload-title" className="text-lg font-semibold">
            Subir fotografía
          </h3>
          {isArchived ? (
            <p className="flex items-center gap-2 text-sm text-gray-500">
              <Lock size={16} /> Paciente archivado: no se pueden subir
              imágenes.
            </p>
          ) : !canUpload ? (
            <p className="flex items-center gap-2 text-sm text-gray-500">
              <Lock size={16} /> No tienes permiso para subir imágenes.
            </p>
          ) : !hasConsent ? (
            <p className="text-sm text-gray-500">
              Registra el consentimiento del paciente para poder subir
              fotografías.
            </p>
          ) : (
            <UploadForm patientId={patientId} />
          )}
        </section>

        <ImageGallery patientId={patientId} />
      </div>
    </Card>
  );
}
