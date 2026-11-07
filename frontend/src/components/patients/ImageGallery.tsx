import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, ChevronLeft, ChevronRight, Eye, History } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";

import Button from "../basic/Button";
import LoadingSpinner from "../basic/LoadingSpinner";
import Modal from "../basic/Modal";
import Textarea from "../basic/Textarea";
import { useAuth } from "../../context/AuthContext";
import { getApiErrorMessage } from "../../services/apiError";
import { getVisits } from "../../services/clinicalVisitService";
import {
  getPatientImageAccessLog,
  getPatientImageFile,
  getPatientImageRevisions,
  getPatientImageThumbnail,
  getPatientImages,
  updatePatientImage,
  voidPatientImage,
} from "../../services/patientImageService";
import type { PatientImage } from "../../types/patientImage";
import ImageMetadataFields from "./ImageMetadataFields";
import {
  GALLERY_PAGE_SIZE,
  IMAGE_ORIGIN_LABELS,
  IMAGE_VIEW_LABELS,
  canModifyImage,
  formatBytes,
  imageMetadataForm,
  patientImagesKey,
  readAsDataUrl,
  toImageMetadata,
} from "./imageUpload";
import { timelineKey } from "./timelineEvents";

const dateTime = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "medium",
  timeStyle: "short",
});
const dateOnly = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "medium",
  timeZone: "UTC",
});

const formatDay = (value: string) =>
  dateOnly.format(new Date(`${value}T00:00:00Z`));

/** Fecha de toma si se registró; si no, la de subida. */
const shownDate = (image: PatientImage) =>
  image.taken_on
    ? formatDay(image.taken_on)
    : dateTime.format(new Date(image.uploaded_at));

const describe = (image: PatientImage) =>
  [
    shownDate(image),
    image.view ? IMAGE_VIEW_LABELS[image.view] : null,
    image.tooth ? `pieza ${image.tooth}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

/** Imagen pedida con el token y mostrada como data URL (sin URL pública). */
function useImageData(
  image: PatientImage,
  variant: "thumbnail" | "file",
): string | undefined {
  const { data } = useQuery({
    queryKey: [...patientImagesKey(image.patient_id), image.id, variant],
    queryFn: async () =>
      readAsDataUrl(
        await (variant === "thumbnail"
          ? getPatientImageThumbnail(image.patient_id, image.id)
          : getPatientImageFile(image.patient_id, image.id)),
      ),
    staleTime: Infinity,
  });
  return data;
}

function Thumbnail({
  image,
  onOpen,
}: {
  image: PatientImage;
  onOpen: () => void;
}) {
  const src = useImageData(image, "thumbnail");
  const voided = image.voided_at !== null;

  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        aria-label={`Ver fotografía del ${describe(image)}${voided ? " (anulada)" : ""}`}
        className="group flex w-full flex-col gap-1 text-left focus:outline-none"
      >
        <span className="relative block aspect-square w-full overflow-hidden rounded-xl bg-gray-100 ring-offset-2 group-focus:ring-2 group-focus:ring-gray-900">
          {src && (
            <img
              src={src}
              alt=""
              className={clsx(
                "h-full w-full object-cover transition group-hover:opacity-90",
                voided && "opacity-40 grayscale",
              )}
            />
          )}
          {voided && (
            <span className="absolute left-2 top-2 rounded-md bg-red-600 px-2 py-0.5 text-xs font-medium text-white">
              Anulada
            </span>
          )}
        </span>
        <span className="text-xs text-gray-600">{describe(image)}</span>
        <span className="text-xs text-gray-500">{image.uploaded_by.name}</span>
      </button>
    </li>
  );
}

type Panel = "edit" | "void" | "revisions" | "access" | null;

function EditPanel({
  image,
  onDone,
}: {
  image: PatientImage;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(() => imageMetadataForm(image));
  const { data: allVisits = [] } = useQuery({
    queryKey: ["patients", image.patient_id, "visits"],
    queryFn: () => getVisits(image.patient_id),
  });
  // Se conserva la consulta actual aunque se haya anulado después.
  const visits = allVisits.filter(
    (visit) => !visit.voided_at || visit.id === image.clinical_visit?.id,
  );

  const mutation = useMutation({
    mutationFn: () => {
      const data = toImageMetadata(form);
      if (!data) throw new Error("Indica el origen de la fotografía.");
      return updatePatientImage(image.patient_id, image.id, {
        ...data,
        base_revision: image.revision,
      });
    },
    onSuccess: () => {
      toast.success("Datos de la fotografía actualizados");
      queryClient.invalidateQueries({
        queryKey: patientImagesKey(image.patient_id),
      });
      queryClient.invalidateQueries({
        queryKey: timelineKey(image.patient_id),
      });
      onDone();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error && !("isAxiosError" in error)
          ? error.message
          : getApiErrorMessage(error, "No se pudieron guardar los cambios"),
      );
      queryClient.invalidateQueries({
        queryKey: patientImagesKey(image.patient_id),
      });
    },
  });

  return (
    <form
      aria-label="Corregir datos de la fotografía"
      className="flex flex-col gap-4 rounded-xl border p-4"
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate();
      }}
    >
      <p className="text-sm text-gray-600">
        El archivo no cambia; la corrección queda en el historial.
      </p>
      <fieldset disabled={mutation.isPending}>
        <ImageMetadataFields value={form} onChange={setForm} visits={visits} />
      </fieldset>
      <div className="flex justify-end gap-3">
        <Button
          variant="secondary"
          onClick={onDone}
          disabled={mutation.isPending}
        >
          Cancelar
        </Button>
        <Button type="submit" disabled={mutation.isPending || !form.origin}>
          {mutation.isPending ? "Guardando..." : "Guardar corrección"}
        </Button>
      </div>
    </form>
  );
}

function VoidPanel({
  image,
  onDone,
}: {
  image: PatientImage;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      voidPatientImage(image.patient_id, image.id, reason.trim()),
    onSuccess: () => {
      toast.success("Fotografía anulada");
      queryClient.invalidateQueries({
        queryKey: patientImagesKey(image.patient_id),
      });
      queryClient.invalidateQueries({
        queryKey: timelineKey(image.patient_id),
      });
      onDone();
    },
    onError: (error) =>
      toast.error(getApiErrorMessage(error, "No se pudo anular la fotografía")),
  });

  return (
    <form
      aria-label="Anular fotografía"
      className="flex flex-col gap-3 rounded-xl border border-red-200 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate();
      }}
    >
      <p className="text-sm text-gray-600">
        La fotografía no se borra: se conserva con el motivo y deja de mostrarse
        en la galería.
      </p>
      <Textarea
        label="Motivo *"
        required
        maxLength={500}
        value={reason}
        disabled={mutation.isPending}
        onChange={(e) => setReason(e.target.value)}
      />
      <div className="flex justify-end gap-3">
        <Button
          variant="secondary"
          onClick={onDone}
          disabled={mutation.isPending}
        >
          Cancelar
        </Button>
        <Button
          type="submit"
          variant="danger"
          disabled={mutation.isPending || !reason.trim()}
        >
          {mutation.isPending ? "Anulando..." : "Anular fotografía"}
        </Button>
      </div>
    </form>
  );
}

function RevisionsPanel({ image }: { image: PatientImage }) {
  const { data: revisions, isLoading } = useQuery({
    queryKey: [...patientImagesKey(image.patient_id), image.id, "revisions"],
    queryFn: () => getPatientImageRevisions(image.patient_id, image.id),
  });
  if (isLoading || !revisions) return <LoadingSpinner />;

  return (
    <ol aria-label="Historial de cambios" className="flex flex-col gap-2">
      {revisions.map((revision) => (
        <li key={revision.revision} className="rounded-lg border p-3 text-sm">
          <p className="font-medium">
            {revision.revision === 1 ? "Alta" : `Revisión ${revision.revision}`}{" "}
            · {revision.edited_by.name} ·{" "}
            {dateTime.format(new Date(revision.edited_at))}
          </p>
          <p className="text-gray-600">
            {[
              revision.origin
                ? IMAGE_ORIGIN_LABELS[revision.origin]
                : "Origen sin registrar",
              revision.view ? IMAGE_VIEW_LABELS[revision.view] : null,
              revision.taken_on
                ? `tomada el ${formatDay(revision.taken_on)}`
                : null,
              revision.tooth ? `pieza ${revision.tooth}` : null,
              revision.clinical_visit_id ? "con consulta" : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </li>
      ))}
    </ol>
  );
}

function AccessPanel({ image }: { image: PatientImage }) {
  const { data: log, isLoading } = useQuery({
    queryKey: [...patientImagesKey(image.patient_id), image.id, "access"],
    queryFn: () => getPatientImageAccessLog(image.patient_id, image.id),
  });
  if (isLoading || !log) return <LoadingSpinner />;

  return log.length === 0 ? (
    <p className="text-sm text-gray-500">Nadie ha abierto el original.</p>
  ) : (
    <ol
      aria-label="Accesos al original"
      className="flex flex-col gap-1 text-sm"
    >
      {log.map((entry, index) => (
        <li key={index}>
          {entry.user.name} · {dateTime.format(new Date(entry.accessed_at))}
        </li>
      ))}
    </ol>
  );
}

function Viewer({
  images,
  index,
  canManage,
  isArchived,
  onNavigate,
  onClose,
}: {
  images: PatientImage[];
  index: number;
  canManage: boolean;
  isArchived: boolean;
  onNavigate: (imageId: number) => void;
  onClose: () => void;
}) {
  const { user } = useAuth();
  const image = images[index];
  const src = useImageData(image, "file");
  const [panel, setPanel] = useState<Panel>(null);
  const canModify = canManage && !isArchived && canModifyImage(image, user);
  const isAdmin = user?.role === "admin";

  const visit = image.clinical_visit;
  const details: [string, string][] = [
    [
      "Fecha de toma",
      image.taken_on ? formatDay(image.taken_on) : "Sin registrar",
    ],
    [
      "Subida",
      `${dateTime.format(new Date(image.uploaded_at))} · ${image.uploaded_by.name}`,
    ],
    [
      "Origen",
      image.origin ? IMAGE_ORIGIN_LABELS[image.origin] : "Sin registrar",
    ],
    ["Vista", image.view ? IMAGE_VIEW_LABELS[image.view] : "Sin especificar"],
    [
      "Consulta",
      visit
        ? `${dateTime.format(new Date(visit.visit_at))} · ${visit.reason}${visit.voided ? " (anulada)" : ""}`
        : "Sin consulta",
    ],
    ["Pieza", image.tooth ? String(image.tooth) : "Sin pieza"],
    [
      "Archivo",
      `${image.width} × ${image.height} px · ${formatBytes(image.size_bytes)}`,
    ],
    ["Revisión", String(image.revision)],
  ];

  const toggle = (next: Panel) => setPanel(panel === next ? null : next);
  const go = (offset: number) => {
    setPanel(null);
    onNavigate(images[index + offset].id);
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={`Fotografía ${index + 1} de ${images.length}`}
    >
      <div className="flex flex-col gap-4">
        {image.voided_at && (
          <div
            role="status"
            className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900"
          >
            Anulada por {image.voided_by?.name} el{" "}
            {dateTime.format(new Date(image.voided_at))} · Motivo:{" "}
            {image.void_reason}
          </div>
        )}

        <div className="flex min-h-64 items-center justify-center rounded-xl bg-gray-900">
          {src ? (
            <img
              src={src}
              alt={`Fotografía clínica del ${describe(image)}`}
              className="max-h-[50vh] w-auto rounded-lg object-contain"
            />
          ) : (
            <LoadingSpinner />
          )}
        </div>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          {details.map(([term, value]) => (
            <div key={term} className="contents">
              <dt className="text-gray-500">{term}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>

        <div className="flex flex-wrap gap-2">
          {canModify && (
            <>
              <Button variant="secondary" onClick={() => toggle("edit")}>
                Corregir datos
              </Button>
              <Button variant="secondary" onClick={() => toggle("void")}>
                <span className="flex items-center gap-1">
                  <Ban size={16} /> Anular
                </span>
              </Button>
            </>
          )}
          <Button
            variant="secondary"
            aria-expanded={panel === "revisions"}
            onClick={() => toggle("revisions")}
          >
            <span className="flex items-center gap-1">
              <History size={16} /> Historial de cambios
            </span>
          </Button>
          {isAdmin && (
            <Button
              variant="secondary"
              aria-expanded={panel === "access"}
              onClick={() => toggle("access")}
            >
              <span className="flex items-center gap-1">
                <Eye size={16} /> Accesos
              </span>
            </Button>
          )}
        </div>

        {panel === "edit" && (
          <EditPanel image={image} onDone={() => setPanel(null)} />
        )}
        {panel === "void" && (
          <VoidPanel image={image} onDone={() => setPanel(null)} />
        )}
        {panel === "revisions" && <RevisionsPanel image={image} />}
        {panel === "access" && <AccessPanel image={image} />}

        {images.length > 1 && (
          <div className="flex justify-between">
            <Button
              variant="secondary"
              disabled={index === 0}
              onClick={() => go(-1)}
            >
              <span className="flex items-center gap-1">
                <ChevronLeft size={16} /> Más reciente
              </span>
            </Button>
            <Button
              variant="secondary"
              disabled={index === images.length - 1}
              onClick={() => go(1)}
            >
              <span className="flex items-center gap-1">
                Más antigua <ChevronRight size={16} />
              </span>
            </Button>
          </div>
        )}
      </div>
    </Modal>
  );
}

interface ImageGalleryProps {
  patientId: number;
  /** Puede corregir o anular (además debe ser quien la subió o admin). */
  canManage: boolean;
  isArchived: boolean;
}

/** Galería de fotografías clínicas del paciente (ODON-174, ODON-178). */
export default function ImageGallery({
  patientId,
  canManage,
  isArchived,
}: ImageGalleryProps) {
  const [visible, setVisible] = useState(GALLERY_PAGE_SIZE);
  const [openId, setOpenId] = useState<number | null>(null);
  const [showVoided, setShowVoided] = useState(false);

  const { data: images = [], isLoading } = useQuery({
    queryKey: patientImagesKey(patientId),
    queryFn: () => getPatientImages(patientId),
  });

  const voidedCount = images.filter((image) => image.voided_at).length;
  const shown = showVoided
    ? images
    : images.filter((image) => !image.voided_at);
  // Si la foto abierta se acaba de anular y quedó oculta, el visor sigue
  // mostrándola dentro de la lista completa.
  const viewerList = shown.some((image) => image.id === openId)
    ? shown
    : images;
  const openIndex = viewerList.findIndex((image) => image.id === openId);

  return (
    <section
      aria-labelledby="image-gallery-title"
      className="flex flex-col gap-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="image-gallery-title" className="text-lg font-semibold">
          Galería{shown.length > 0 ? ` (${shown.length})` : ""}
        </h3>
        {voidedCount > 0 && (
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={showVoided}
              onChange={(e) => setShowVoided(e.target.checked)}
            />
            Mostrar anuladas ({voidedCount})
          </label>
        )}
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : shown.length === 0 ? (
        <p className="text-sm text-gray-500">
          {images.length === 0
            ? "Aún no hay fotografías de este paciente."
            : "No hay fotografías vigentes."}
        </p>
      ) : (
        <>
          <ul
            aria-label="Fotografías del paciente"
            className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
          >
            {shown.slice(0, visible).map((image) => (
              <Thumbnail
                key={image.id}
                image={image}
                onOpen={() => setOpenId(image.id)}
              />
            ))}
          </ul>
          {shown.length > visible && (
            <div className="flex justify-center">
              <Button
                variant="secondary"
                onClick={() => setVisible((n) => n + GALLERY_PAGE_SIZE)}
              >
                Ver más ({shown.length - visible})
              </Button>
            </div>
          )}
        </>
      )}

      {openIndex >= 0 && (
        <Viewer
          key={openId}
          images={viewerList}
          index={openIndex}
          canManage={canManage}
          isArchived={isArchived}
          onNavigate={setOpenId}
          onClose={() => setOpenId(null)}
        />
      )}
    </section>
  );
}
