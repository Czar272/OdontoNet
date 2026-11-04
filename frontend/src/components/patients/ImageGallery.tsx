import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import Button from "../basic/Button";
import LoadingSpinner from "../basic/LoadingSpinner";
import Modal from "../basic/Modal";
import {
  getPatientImageFile,
  getPatientImageThumbnail,
  getPatientImages,
} from "../../services/patientImageService";
import type { PatientImage } from "../../types/patientImage";
import {
  GALLERY_PAGE_SIZE,
  formatBytes,
  patientImagesKey,
  readAsDataUrl,
} from "./imageUpload";

const dateTime = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "medium",
  timeStyle: "short",
});

const describe = (image: PatientImage) =>
  [
    dateTime.format(new Date(image.uploaded_at)),
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

  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        aria-label={`Ver fotografía del ${describe(image)}`}
        className="group flex w-full flex-col gap-1 text-left focus:outline-none"
      >
        <span className="block aspect-square w-full overflow-hidden rounded-xl bg-gray-100 ring-offset-2 group-focus:ring-2 group-focus:ring-gray-900">
          {src && (
            <img
              src={src}
              alt=""
              className="h-full w-full object-cover transition group-hover:opacity-90"
            />
          )}
        </span>
        <span className="text-xs text-gray-600">{describe(image)}</span>
        <span className="text-xs text-gray-500">{image.uploaded_by.name}</span>
      </button>
    </li>
  );
}

function Viewer({
  images,
  index,
  onNavigate,
  onClose,
}: {
  images: PatientImage[];
  index: number;
  onNavigate: (index: number) => void;
  onClose: () => void;
}) {
  const image = images[index];
  const src = useImageData(image, "file");
  const details: [string, string][] = [
    ["Fecha", dateTime.format(new Date(image.uploaded_at))],
    ["Subida por", image.uploaded_by.name],
    [
      "Consulta",
      image.clinical_visit
        ? `${dateTime.format(new Date(image.clinical_visit.visit_at))} · ${image.clinical_visit.reason}${image.clinical_visit.voided ? " (anulada)" : ""}`
        : "Sin consulta",
    ],
    ["Pieza", image.tooth ? String(image.tooth) : "Sin pieza"],
    [
      "Archivo",
      `${image.width} × ${image.height} px · ${formatBytes(image.size_bytes)}`,
    ],
  ];

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={`Fotografía ${index + 1} de ${images.length}`}
    >
      <div className="flex flex-col gap-4">
        <div className="flex min-h-64 items-center justify-center rounded-xl bg-gray-900">
          {src ? (
            <img
              src={src}
              alt={`Fotografía clínica del ${describe(image)}`}
              className="max-h-[60vh] w-auto rounded-lg object-contain"
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

        {images.length > 1 && (
          <div className="flex justify-between">
            <Button
              variant="secondary"
              disabled={index === 0}
              onClick={() => onNavigate(index - 1)}
            >
              <span className="flex items-center gap-1">
                <ChevronLeft size={16} /> Más reciente
              </span>
            </Button>
            <Button
              variant="secondary"
              disabled={index === images.length - 1}
              onClick={() => onNavigate(index + 1)}
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

/** Galería de fotografías clínicas del paciente (ODON-174). */
export default function ImageGallery({ patientId }: { patientId: number }) {
  const [visible, setVisible] = useState(GALLERY_PAGE_SIZE);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const { data: images = [], isLoading } = useQuery({
    queryKey: patientImagesKey(patientId),
    queryFn: () => getPatientImages(patientId),
  });

  return (
    <section
      aria-labelledby="image-gallery-title"
      className="flex flex-col gap-3"
    >
      <h3 id="image-gallery-title" className="text-lg font-semibold">
        Galería{images.length > 0 ? ` (${images.length})` : ""}
      </h3>

      {isLoading ? (
        <LoadingSpinner />
      ) : images.length === 0 ? (
        <p className="text-sm text-gray-500">
          Aún no hay fotografías de este paciente.
        </p>
      ) : (
        <>
          <ul
            aria-label="Fotografías del paciente"
            className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
          >
            {images.slice(0, visible).map((image, index) => (
              <Thumbnail
                key={image.id}
                image={image}
                onOpen={() => setOpenIndex(index)}
              />
            ))}
          </ul>
          {images.length > visible && (
            <div className="flex justify-center">
              <Button
                variant="secondary"
                onClick={() => setVisible((n) => n + GALLERY_PAGE_SIZE)}
              >
                Ver más ({images.length - visible})
              </Button>
            </div>
          )}
        </>
      )}

      {openIndex !== null && images[openIndex] && (
        <Viewer
          images={images}
          index={openIndex}
          onNavigate={setOpenIndex}
          onClose={() => setOpenIndex(null)}
        />
      )}
    </section>
  );
}
