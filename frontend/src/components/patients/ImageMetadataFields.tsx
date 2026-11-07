import Input from "../basic/Input";
import Select from "../basic/Select";
import type { ClinicalVisit } from "../../types/clinicalVisit";
import type { ImageOrigin, ImageView } from "../../types/patientImage";
import ToothChart from "./ToothChart";
import {
  IMAGE_ORIGIN_LABELS,
  IMAGE_VIEW_LABELS,
  todayLocal,
  type ImageMetadataForm,
} from "./imageUpload";

const dateTime = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "medium",
  timeStyle: "short",
});

interface ImageMetadataFieldsProps {
  value: ImageMetadataForm;
  onChange: (value: ImageMetadataForm) => void;
  /** Consultas vigentes del paciente. */
  visits: ClinicalVisit[];
}

/** Origen, vista, fecha de toma, consulta y pieza (ODON-178). */
export default function ImageMetadataFields({
  value,
  onChange,
  visits,
}: ImageMetadataFieldsProps) {
  const set = <K extends keyof ImageMetadataForm>(
    key: K,
    next: ImageMetadataForm[K],
  ) => onChange({ ...value, [key]: next });

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Select
          label="Origen *"
          required
          value={value.origin}
          onChange={(e) => set("origin", e.target.value as ImageOrigin | "")}
        >
          <option value="">Elige el origen</option>
          {Object.entries(IMAGE_ORIGIN_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </Select>
        <Select
          label="Tipo de vista"
          value={value.view}
          onChange={(e) => set("view", e.target.value as ImageView | "")}
        >
          <option value="">Sin especificar</option>
          {Object.entries(IMAGE_VIEW_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </Select>
        <Input
          label="Fecha de toma"
          type="date"
          max={todayLocal()}
          value={value.taken_on}
          onChange={(e) => set("taken_on", e.target.value)}
        />
      </div>

      <Select
        label="Consulta (opcional)"
        value={value.clinical_visit_id}
        onChange={(e) => set("clinical_visit_id", e.target.value)}
      >
        <option value="">Sin consulta</option>
        {visits.map((visit) => (
          <option key={visit.id} value={visit.id}>
            {dateTime.format(new Date(visit.visit_at))} · {visit.reason}
          </option>
        ))}
      </Select>

      <ToothChart
        value={value.tooth}
        onChange={(tooth) => set("tooth", tooth)}
        hint={
          value.tooth
            ? `Pieza ${value.tooth}. Tócala de nuevo para quitarla.`
            : "Pieza (opcional): toca una pieza para asociarla a la foto."
        }
      />
    </div>
  );
}
