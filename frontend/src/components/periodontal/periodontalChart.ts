/**
 * Reglas y geometría del periodontograma (ODON-9). Espejo de
 * backend/app/models/periodontal.py: piezas, sitios, rangos y furcaciones.
 */
import type {
  ExamContentDTO,
  ExamSummary,
  Furcation,
  FurcationEntrance,
  PeriodontalExam,
  SiteCode,
  SiteData,
  ToothData,
} from "../../types/periodontal";

// Orden de dibujo: vista del clínico frente al paciente.
export const UPPER_TEETH = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
export const LOWER_TEETH = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];
export const PERMANENT_TEETH = [...UPPER_TEETH, ...LOWER_TEETH];
export const SITES: SiteCode[] = ["mb", "b", "db", "ml", "l", "dl"];

export const PROBING_DEPTH_RANGE = [0, 15] as const;
export const GINGIVAL_MARGIN_RANGE = [-15, 5] as const;
export const MOBILITY_RANGE = [0, 3] as const;
export const FURCATION_GRADES = [1, 2, 3] as const;
/** Umbral descriptivo de «sitio profundo» del resumen. */
export const DEEP_SITE_MM = 4;
/** Cambio de sondaje que se resalta al comparar dos exámenes (ODON-194). */
export const SIGNIFICANT_CHANGE_MM = 2;

const UPPER_MOLARS = [16, 17, 18, 26, 27, 28];
const LOWER_MOLARS = [36, 37, 38, 46, 47, 48];

export const FURCATION_ENTRANCES: Record<number, FurcationEntrance[]> = Object.fromEntries([
  ...UPPER_MOLARS.map((tooth) => [tooth, ["b", "mp", "dp"]]),
  ...LOWER_MOLARS.map((tooth) => [tooth, ["b", "l"]]),
]);

/**
 * Entradas de furcación de una cara en orden de pantalla: lo distal hacia
 * afuera, como los sitios (en los cuadrantes 1 y 4, distal a la izquierda).
 */
export function displayEntrances(tooth: number, face: Face): FurcationEntrance[] {
  const entrances = (FURCATION_ENTRANCES[tooth] ?? []).filter((entrance) =>
    face === "buccal" ? entrance === "b" : entrance !== "b",
  );
  const quadrant = Math.floor(tooth / 10);
  return quadrant === 1 || quadrant === 4 ? [...entrances].reverse() : entrances;
}

export const FURCATION_LABELS: Record<FurcationEntrance, string> = {
  b: "Vestibular",
  mp: "Mesiopalatina",
  dp: "Distopalatina",
  l: "Lingual",
};

export type Face = "buccal" | "lingual";
export type Arch = "upper" | "lower";

export const isUpper = (tooth: number) => tooth < 30;
export const archOf = (tooth: number): Arch => (isUpper(tooth) ? "upper" : "lower");

/** Nombre de la cara palatina o lingual según la arcada. */
export const innerFaceLabel = (arch: Arch) => (arch === "upper" ? "Palatino" : "Lingual");

/**
 * Sitios de una cara en orden de izquierda a derecha en pantalla. Lo distal
 * queda siempre hacia afuera: en los cuadrantes 1 y 4 (izquierda de la
 * pantalla) se lee distal → mesial; en los 2 y 3, mesial → distal.
 */
export function displaySites(tooth: number, face: Face): SiteCode[] {
  const [mesial, center, distal]: SiteCode[] =
    face === "buccal" ? ["mb", "b", "db"] : ["ml", "l", "dl"];
  const quadrant = Math.floor(tooth / 10);
  return quadrant === 1 || quadrant === 4
    ? [distal, center, mesial]
    : [mesial, center, distal];
}

export const SITE_LABELS: Record<SiteCode, string> = {
  mb: "mesiovestibular",
  b: "vestibular",
  db: "distovestibular",
  ml: "mesiolingual",
  l: "lingual",
  dl: "distolingual",
};

/** Etiqueta accesible del sitio, con «palatino» en la arcada superior. */
export function siteLabel(tooth: number, site: SiteCode): string {
  const label = SITE_LABELS[site];
  return isUpper(tooth) ? label.replace("lingual", "palatino") : label;
}

export const emptySite = (): SiteData => ({
  probing_depth: null,
  gingival_margin: null,
  bleeding: false,
  suppuration: false,
  plaque: false,
});

export const emptyFurcation = (): Furcation => ({ b: null, mp: null, dp: null, l: null });

export const emptyTooth = (tooth: number): ToothData => ({
  tooth,
  missing: false,
  implant: false,
  mobility: null,
  furcation: emptyFurcation(),
  note: null,
  sites: Object.fromEntries(SITES.map((site) => [site, emptySite()])) as Record<SiteCode, SiteData>,
});

export const emptyChart = (): ToothData[] => PERMANENT_TEETH.map(emptyTooth);

/** Contenido editable de un examen recibido de la API. */
export function chartFromExam(exam: PeriodontalExam): ToothData[] {
  const byTooth = new Map(exam.teeth.map((tooth) => [tooth.tooth, tooth]));
  return PERMANENT_TEETH.map((number) => {
    const tooth = byTooth.get(number);
    if (!tooth) return emptyTooth(number);
    return {
      tooth: number,
      missing: tooth.missing,
      implant: tooth.implant,
      mobility: tooth.mobility,
      furcation: { ...emptyFurcation(), ...tooth.furcation },
      note: tooth.note,
      source: tooth.source ?? "manual",
      sites: Object.fromEntries(
        SITES.map((site) => {
          const { probing_depth, gingival_margin, bleeding, suppuration, plaque, source } = tooth.sites[site];
          return [site, { probing_depth, gingival_margin, bleeding, suppuration, plaque, source: source ?? "manual" }];
        }),
      ) as Record<SiteCode, SiteData>,
    };
  });
}

const siteIsEmpty = (site: SiteData) =>
  site.probing_depth === null &&
  site.gingival_margin === null &&
  !site.bleeding &&
  !site.suppuration &&
  !site.plaque;

const toothIsEmpty = (tooth: ToothData) =>
  !tooth.missing &&
  !tooth.implant &&
  tooth.mobility === null &&
  Object.values(tooth.furcation).every((grade) => grade === null) &&
  !tooth.note &&
  SITES.every((site) => siteIsEmpty(tooth.sites[site]));

/** Solo se envían las piezas con algún dato: el backend completa el resto vacío. */
export function toContent(
  examDate: string,
  clinicalVisitId: number | null,
  notes: string,
  chart: ToothData[],
): ExamContentDTO {
  return {
    exam_date: examDate,
    clinical_visit_id: clinicalVisitId,
    notes: notes.trim() || null,
    teeth: chart.filter((tooth) => !toothIsEmpty(tooth)),
  };
}

export const attachmentLevel = (site: SiteData): number | null =>
  site.probing_depth === null || site.gingival_margin === null
    ? null
    : site.probing_depth - site.gingival_margin;

/**
 * Redondeo como el round() de Python (empates al par), para que el resumen en
 * vivo coincida con el que devuelve el backend.
 */
export const round = (value: number, digits: number) => {
  const factor = 10 ** digits;
  const scaled = value * factor;
  const floor = Math.floor(scaled);
  const diff = scaled - floor;
  const EPS = 1e-9;
  let result: number;
  if (diff > 0.5 + EPS) result = floor + 1;
  else if (diff < 0.5 - EPS) result = floor;
  else result = floor % 2 === 0 ? floor : floor + 1;
  return result / factor;
};

/** Espejo de periodontal_service.summarize: sitios con sondaje de piezas presentes. */
export function summarize(chart: ToothData[]): ExamSummary {
  const present = chart.filter((tooth) => !tooth.missing);
  const measured = present.flatMap((tooth) =>
    SITES.map((site) => tooth.sites[site]).filter((site) => site.probing_depth !== null),
  );
  const levels = measured.map(attachmentLevel).filter((level): level is number => level !== null);
  const pct = (count: number) => (measured.length ? round((100 * count) / measured.length, 1) : null);
  const mean = (values: number[]) =>
    values.length ? round(values.reduce((a, b) => a + b, 0) / values.length, 2) : null;
  return {
    present_teeth: present.length,
    measured_sites: measured.length,
    mean_probing_depth: mean(measured.map((site) => site.probing_depth as number)),
    mean_attachment_level: mean(levels),
    bleeding_pct: pct(measured.filter((site) => site.bleeding).length),
    plaque_pct: pct(measured.filter((site) => site.plaque).length),
    deep_sites_pct: pct(measured.filter((site) => (site.probing_depth as number) >= DEEP_SITE_MM).length),
    default_sites: measured.filter((site) => site.source === "default").length,
  };
}

/** Error de validación de un valor escrito, o null si es válido o vacío. */
export function valueError(
  kind: "probing_depth" | "gingival_margin",
  value: number | null,
): string | null {
  if (value === null) return null;
  const [min, max] = kind === "probing_depth" ? PROBING_DEPTH_RANGE : GINGIVAL_MARGIN_RANGE;
  if (!Number.isInteger(value) || value < min || value > max) {
    return kind === "probing_depth"
      ? `El sondaje va de ${min} a ${max} mm.`
      : `El margen va de ${min} a +${max} mm.`;
  }
  return null;
}

// --- Geometría del dibujo ------------------------------------------------------

export type ToothKind = "incisor" | "canine" | "premolar" | "molar";

export function toothKind(tooth: number): ToothKind {
  const piece = tooth % 10;
  if (piece <= 2) return "incisor";
  if (piece === 3) return "canine";
  if (piece <= 5) return "premolar";
  return "molar";
}

/** Raíces visibles en la vista vestibular o lingual. */
export function rootCount(tooth: number): number {
  const kind = toothKind(tooth);
  if (kind === "molar") return 2;
  if (kind === "premolar" && isUpper(tooth) && tooth % 10 === 4) return 2;
  return 1;
}

/** Píxeles por milímetro en el dibujo. */
export const MM = 3;
export const TOOTH_WIDTH = 48;
/**
 * Alto del dibujo de una cara; la UAC queda en CEJ_Y. Hacia apical caben
 * 30 mm (margen −15 más sondaje 15), así ninguna bolsa se corta.
 */
export const FACE_HEIGHT = 186;
export const CEJ_Y = 93;

/** x de cada sitio dentro de la columna de la pieza (izquierda, centro, derecha). */
export const SITE_X = [0.2, 0.5, 0.8].map((ratio) => ratio * TOOTH_WIDTH);

/** Dirección de la raíz en pantalla: −1 hacia arriba, +1 hacia abajo. */
export type Apical = -1 | 1;

/**
 * Como en la herramienta de referencia, las coronas de las dos caras de una
 * arcada se enfrentan: arriba la cara externa de la arcada superior
 * (vestibular, raíces hacia arriba) y su cara palatina debajo (raíces hacia
 * abajo); en la inferior, la lingual arriba y la vestibular abajo.
 */
export function apicalOf(arch: Arch, face: Face): Apical {
  if (arch === "upper") return face === "buccal" ? -1 : 1;
  return face === "lingual" ? -1 : 1;
}

/** y del margen gingival: negativo (recesión) lo lleva hacia apical. */
export function marginY(apical: Apical, gingivalMargin: number | null): number {
  return CEJ_Y - apical * (gingivalMargin ?? 0) * MM;
}

/** y del fondo de la bolsa: el sondaje se mide desde el margen hacia apical. */
export function pocketY(apical: Apical, site: SiteData): number {
  return marginY(apical, site.gingival_margin) + apical * (site.probing_depth ?? 0) * MM;
}

/**
 * Silueta propia de una pieza (corona y raíces) como path SVG, dibujada en una
 * columna de TOOTH_WIDTH con la UAC en CEJ_Y. Simplificada a propósito: sirve
 * de referencia visual para las líneas de margen y bolsa, no es anatómica.
 */
export function toothPath(tooth: number, apical: Apical): string {
  const kind = toothKind(tooth);
  const w = TOOTH_WIDTH;
  const s = apical; // hacia la raíz
  const crown = { incisor: 40, canine: 44, premolar: 36, molar: 32 }[kind];
  const root = { incisor: 52, canine: 64, premolar: 54, molar: 50 }[kind];
  const half = { incisor: 15, canine: 15, premolar: 16, molar: 20 }[kind];
  const cx = w / 2;
  const left = cx - half;
  const right = cx + half;
  const edge = CEJ_Y - s * crown; // borde incisal u oclusal
  const apex = CEJ_Y + s * root;

  // Corona: más ancha que el cuello, con borde redondeado.
  const crownPath = [
    `M ${left + 3} ${CEJ_Y}`,
    `C ${left - 2} ${CEJ_Y - s * crown * 0.4}, ${left} ${edge}, ${cx} ${edge}`,
    `C ${right} ${edge}, ${right + 2} ${CEJ_Y - s * crown * 0.4}, ${right - 3} ${CEJ_Y}`,
  ].join(" ");

  const roots = rootCount(tooth);
  if (roots === 1) {
    const rootPath = [
      `M ${right - 3} ${CEJ_Y}`,
      `C ${right - 4} ${CEJ_Y + s * root * 0.6}, ${cx + 3} ${apex}, ${cx} ${apex}`,
      `C ${cx - 3} ${apex}, ${left + 4} ${CEJ_Y + s * root * 0.6}, ${left + 3} ${CEJ_Y}`,
    ].join(" ");
    return `${crownPath} ${rootPath.replace(/^M [^C]+/, "")} Z`;
  }
  // Dos raíces con la furcación entre ellas.
  const furcation = CEJ_Y + s * root * 0.3;
  const mid = cx;
  return [
    crownPath,
    `C ${right - 2} ${CEJ_Y + s * root * 0.5}, ${right - 4} ${apex}, ${right - 8} ${apex}`,
    `C ${right - 12} ${apex}, ${mid + 3} ${CEJ_Y + s * root * 0.5}, ${mid} ${furcation}`,
    `C ${mid - 3} ${CEJ_Y + s * root * 0.5}, ${left + 12} ${apex}, ${left + 8} ${apex}`,
    `C ${left + 4} ${apex}, ${left + 2} ${CEJ_Y + s * root * 0.5}, ${left + 3} ${CEJ_Y}`,
    "Z",
  ].join(" ");
}

/** Solo la corona de la pieza (para dibujar la corona sobre un implante). */
export function crownPath(tooth: number, apical: Apical): string {
  const path = toothPath(tooth, apical);
  // Los dos primeros tramos curvos del path son la corona; se cierra en el cuello.
  const parts = path.split(" C ");
  return `${parts[0]} C ${parts[1]} C ${parts[2].split(" C ")[0].replace(/ Z$/, "")} Z`;
}

/** Implante: tornillo bajo una corona, en lugar de raíces. */
export function implantPath(apical: Apical): string {
  const s = apical;
  const cx = TOOTH_WIDTH / 2;
  const top = CEJ_Y;
  const bottom = CEJ_Y + s * 52;
  const threads: string[] = [];
  for (let i = 0; i < 6; i += 1) {
    const y = top + s * (6 + i * 8);
    threads.push(`M ${cx - 8} ${y} L ${cx + 8} ${y + s * 3}`);
  }
  return [
    `M ${cx - 7} ${top} L ${cx - 5} ${bottom} L ${cx + 5} ${bottom} L ${cx + 7} ${top} Z`,
    ...threads,
  ].join(" ");
}

export const today = () => {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
};

// --- Valores de salud (ODON-262) ---------------------------------------------

/**
 * Valores que se proponen para los sitios vacíos de piezas sanas. Referencia:
 * definición de salud periodontal del World Workshop 2017 (Chapple et al.,
 * 2018): sondaje ≤ 3 mm, sangrado en menos del 10 % de los sitios, sin pérdida
 * de inserción ni ósea; surco sano de 1–3 mm. Ojo: con la convención del margen
 * (0 = en la UAC), sondaje 2 y margen 0 dan NIC 2; en un periodonto intacto la
 * encía queda coronal a la UAC (margen positivo, NIC ≈ 0). Los valores son una
 * propuesta que el profesional elige antes de aplicar; no hay valores propios
 * de la población guatemalteca.
 */
export interface HealthyValues {
  probingDepth: number;
  gingivalMargin: number;
  /** También movilidad 0 en las piezas que no la tienen registrada. */
  mobility: boolean;
}

/**
 * Propuesta inicial del llenado con valores de salud (ODON-277, provisional hasta que la confirme
 * un odontólogo): sondaje 2 y margen +2. Con la convención del sistema (margen con signo respecto a
 * la UAC, NIC = sondaje − margen) da NIC 0: encía coronal a la UAC, sin pérdida de inserción. El
 * valor anterior (margen 0) daba NIC 2 mm ficticio en cada sitio llenado.
 */
export const DEFAULT_HEALTHY: HealthyValues = { probingDepth: 2, gingivalMargin: 2, mobility: true };
export const HEALTHY_PROBING_OPTIONS = [1, 2, 3];
export const HEALTHY_MARGIN_OPTIONS = [0, 1, 2, 3];

/**
 * Valores predeterminados que el profesional todavía no revisó (ODON-277): sitios con origen
 * `default` de piezas presentes y piezas cuya movilidad sigue siendo la predeterminada.
 */
export function countUnreviewedDefaults(chart: ToothData[]): { sites: number; mobility: number } {
  let sites = 0;
  let mobility = 0;
  for (const tooth of chart) {
    if (tooth.missing) continue;
    for (const site of SITES) if (tooth.sites[site].source === "default") sites += 1;
    if (tooth.source === "default" && tooth.mobility !== null) mobility += 1;
  }
  return { sites, mobility };
}

/** Aviso para confirmar la finalización con valores predeterminados sin revisar (no la bloquea). */
export function unreviewedMessage({ sites, mobility }: { sites: number; mobility: number }): string {
  const parts = [];
  if (sites > 0) parts.push(sites === 1 ? "1 sitio" : `${sites} sitios`);
  if (mobility > 0) parts.push(mobility === 1 ? "la movilidad de 1 pieza" : `la movilidad de ${mobility} piezas`);
  if (!parts.length) return "";
  // El sujeto es plural si hay varios sitios, o sitios y movilidad juntos; «la movilidad de N piezas» es singular.
  const plural = sites > 1 || (sites > 0 && mobility > 0);
  return `Atención: ${parts.join(" y ")} ${plural ? "tienen" : "tiene"} un valor predeterminado sin revisar. `
    + "Se guardarán como valores asumidos, no medidos; el editor y el PDF los muestran en gris cursiva.";
}

/**
 * Llena con valores de salud solo los sitios vacíos de piezas presentes y no
 * implantes, marcándolos como predeterminados. Nunca cambia lo ya escrito.
 * Devuelve el nuevo contenido y cuántos sitios llenó.
 */
export function fillHealthy(
  chart: ToothData[],
  values: HealthyValues,
): { chart: ToothData[]; filled: number; mobilityFilled: number } {
  let filled = 0;
  let mobilityFilled = 0;
  const next = chart.map((tooth) => {
    if (tooth.missing || tooth.implant) return tooth;
    const sites = { ...tooth.sites };
    for (const site of SITES) {
      const current = sites[site];
      const empty =
        current.probing_depth === null &&
        current.gingival_margin === null &&
        !current.bleeding &&
        !current.suppuration &&
        !current.plaque;
      if (!empty) continue;
      sites[site] = {
        ...current,
        probing_depth: values.probingDepth,
        gingival_margin: values.gingivalMargin,
        source: "default",
      };
      filled += 1;
    }
    const fillMobility = values.mobility && tooth.mobility === null;
    if (fillMobility) mobilityFilled += 1;
    return {
      ...tooth,
      sites,
      ...(fillMobility ? { mobility: 0, source: "default" as const } : {}),
    };
  });
  return { chart: next, filled, mobilityFilled };
}

