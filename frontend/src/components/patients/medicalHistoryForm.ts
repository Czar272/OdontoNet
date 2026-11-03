import type {
  ConditionKey,
  MedicalHistory,
  MedicalHistoryData,
  SaveMedicalHistoryDTO,
  SmokingStatus,
} from "../../types/medicalHistory";

/** Mismo orden que MEDICAL_CONDITIONS en el backend. */
export const CONDITIONS: { key: ConditionKey; label: string }[] = [
  { key: "diabetes", label: "Diabetes" },
  { key: "hypertension", label: "Hipertensión" },
  { key: "heart_disease", label: "Cardiopatía" },
  {
    key: "bleeding_disorder",
    label: "Trastornos de coagulación / anticoagulantes",
  },
  { key: "respiratory_disease", label: "Enfermedad respiratoria" },
  { key: "liver_kidney_disease", label: "Enfermedad hepática o renal" },
  { key: "immunosuppression", label: "Inmunosupresión" },
  { key: "pregnancy_lactation", label: "Embarazo o lactancia" },
];

export const SMOKING_LABELS: Record<SmokingStatus, string> = {
  never: "No fuma",
  former: "Exfumador",
  current: "Fuma",
};

/** "" = sin dato. */
export type TriState = "" | "yes" | "no";

export const TRI_STATE_OPTIONS: { value: TriState; label: string }[] = [
  { value: "", label: "Sin dato" },
  { value: "no", label: "No" },
  { value: "yes", label: "Sí" },
];

export interface MedicalHistoryFormData {
  conditions: Record<ConditionKey, { present: TriState; detail: string }>;
  other_conditions: string;
  allergies: string;
  current_medications: string;
  smoking_status: "" | SmokingStatus;
  cigarettes_per_day: string;
  alcohol: TriState;
  alcohol_detail: string;
  bruxism: TriState;
  chief_complaint: string;
  last_dental_visit: string;
  previous_treatments: string;
  brushing_per_day: string;
  uses_floss: TriState;
  gum_bleeding: TriState;
  notes: string;
}

export type TextField = Exclude<keyof MedicalHistoryFormData, "conditions">;

const toTri = (value: boolean | null | undefined): TriState =>
  value === true ? "yes" : value === false ? "no" : "";

const fromTri = (value: TriState): boolean | null =>
  value === "yes" ? true : value === "no" ? false : null;

const toText = (value: string | number | null | undefined): string =>
  value === null || value === undefined ? "" : String(value);

const fromText = (value: string): string | null => value.trim() || null;

const fromNumber = (value: string): number | null =>
  value.trim() === "" ? null : Number(value);

export function initialMedicalHistoryForm(
  history: MedicalHistory | null,
): MedicalHistoryFormData {
  const conditions = Object.fromEntries(
    CONDITIONS.map(({ key }) => {
      const entry = history?.conditions[key];
      return [
        key,
        { present: toTri(entry?.present), detail: toText(entry?.detail) },
      ];
    }),
  ) as MedicalHistoryFormData["conditions"];

  return {
    conditions,
    other_conditions: toText(history?.other_conditions),
    allergies: toText(history?.allergies),
    current_medications: toText(history?.current_medications),
    smoking_status: history?.smoking_status ?? "",
    cigarettes_per_day: toText(history?.cigarettes_per_day),
    alcohol: toTri(history?.alcohol),
    alcohol_detail: toText(history?.alcohol_detail),
    bruxism: toTri(history?.bruxism),
    chief_complaint: toText(history?.chief_complaint),
    last_dental_visit: toText(history?.last_dental_visit),
    previous_treatments: toText(history?.previous_treatments),
    brushing_per_day: toText(history?.brushing_per_day),
    uses_floss: toTri(history?.uses_floss),
    gum_bleeding: toTri(history?.gum_bleeding),
    notes: toText(history?.notes),
  };
}

/** Contenido a guardar: vacío = sin dato; cigarrillos solo si fuma. */
export function buildMedicalHistoryData(
  form: MedicalHistoryFormData,
): MedicalHistoryData {
  const conditions = Object.fromEntries(
    CONDITIONS.map(({ key }) => [
      key,
      {
        present: fromTri(form.conditions[key].present),
        detail: fromText(form.conditions[key].detail),
      },
    ]),
  ) as MedicalHistoryData["conditions"];

  return {
    conditions,
    other_conditions: fromText(form.other_conditions),
    allergies: fromText(form.allergies),
    current_medications: fromText(form.current_medications),
    smoking_status: form.smoking_status || null,
    cigarettes_per_day:
      form.smoking_status === "current"
        ? fromNumber(form.cigarettes_per_day)
        : null,
    alcohol: fromTri(form.alcohol),
    alcohol_detail: fromText(form.alcohol_detail),
    bruxism: fromTri(form.bruxism),
    chief_complaint: fromText(form.chief_complaint),
    last_dental_visit: fromText(form.last_dental_visit),
    previous_treatments: fromText(form.previous_treatments),
    brushing_per_day: fromNumber(form.brushing_per_day),
    uses_floss: fromTri(form.uses_floss),
    gum_bleeding: fromTri(form.gum_bleeding),
    notes: fromText(form.notes),
  };
}

export function buildSaveMedicalHistory(
  form: MedicalHistoryFormData,
  current: MedicalHistory | null,
): SaveMedicalHistoryDTO {
  return {
    ...buildMedicalHistoryData(form),
    base_version: current?.version ?? null,
  };
}

/** true si guardar no cambiaría nada respecto de la versión vigente. */
export function isUnchanged(
  form: MedicalHistoryFormData,
  current: MedicalHistory | null,
): boolean {
  return (
    JSON.stringify(buildMedicalHistoryData(form)) ===
    JSON.stringify(buildMedicalHistoryData(initialMedicalHistoryForm(current)))
  );
}
