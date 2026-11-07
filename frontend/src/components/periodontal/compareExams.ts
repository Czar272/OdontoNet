import type { ExamSummary, PeriodontalExam, SiteCode } from "../../types/periodontal";
import { PERMANENT_TEETH, SIGNIFICANT_CHANGE_MM, SITES } from "./periodontalChart";

/** Cambio de un sitio entre dos exámenes (ODON-194). */
export interface SiteChange {
  tooth: number;
  site: SiteCode;
  before: { probing_depth: number | null; gingival_margin: number | null; attachment_level: number | null; bleeding: boolean };
  after: { probing_depth: number | null; gingival_margin: number | null; attachment_level: number | null; bleeding: boolean };
  /** Diferencia de sondaje (después − antes), si ambos existen. */
  probingDelta: number | null;
  attachmentDelta: number | null;
  /** |Δ sondaje| ≥ umbral. */
  significant: boolean;
}

export interface ToothStatusChange {
  tooth: number;
  change: "lost" | "implant" | "natural" | "restored";
}

export interface ExamComparison {
  changes: SiteChange[];
  significant: SiteChange[];
  /** Piezas con al menos un cambio significativo. */
  highlighted: Set<number>;
  toothChanges: ToothStatusChange[];
  summaryDelta: Partial<Record<keyof ExamSummary, number | null>>;
}

/** Ordena dos exámenes por fecha (y por id si tienen la misma fecha). */
export function chronological<T extends { exam_date: string; id: number }>(a: T, b: T): [T, T] {
  if (a.exam_date !== b.exam_date) return a.exam_date < b.exam_date ? [a, b] : [b, a];
  return a.id < b.id ? [a, b] : [b, a];
}

const delta = (after: number | null, before: number | null) =>
  after === null || before === null ? null : Math.round((after - before) * 100) / 100;

/**
 * Compara dos exámenes sitio a sitio: `before` es el anterior y `after` el
 * más reciente. Solo informa diferencias; no interpreta ni diagnostica.
 */
export function compareExams(first: PeriodontalExam, second: PeriodontalExam): ExamComparison {
  // Siempre del más antiguo al más reciente, sin importar el orden de elección.
  const [before, after] = chronological(first, second);
  const prev = new Map(before.teeth.map((tooth) => [tooth.tooth, tooth]));
  const next = new Map(after.teeth.map((tooth) => [tooth.tooth, tooth]));
  const changes: SiteChange[] = [];
  const toothChanges: ToothStatusChange[] = [];

  for (const number of PERMANENT_TEETH) {
    const a = prev.get(number);
    const b = next.get(number);
    if (!a || !b) continue;
    if (!a.missing && b.missing) toothChanges.push({ tooth: number, change: "lost" });
    else if (!a.implant && b.implant) toothChanges.push({ tooth: number, change: "implant" });
    else if (a.implant && !b.implant && !b.missing) toothChanges.push({ tooth: number, change: "natural" });
    else if (a.missing && !b.missing) toothChanges.push({ tooth: number, change: "restored" });
    // Sin pieza en alguno de los dos, o pieza natural ↔ implante: no es la misma
    // estructura, así que sus sitios no se comparan.
    if (a.missing || b.missing || a.implant !== b.implant) continue;

    for (const site of SITES) {
      const s0 = a.sites[site];
      const s1 = b.sites[site];
      const same =
        s0.probing_depth === s1.probing_depth &&
        s0.gingival_margin === s1.gingival_margin &&
        s0.bleeding === s1.bleeding;
      if (same) continue;
      const probingDelta = delta(s1.probing_depth, s0.probing_depth);
      changes.push({
        tooth: number,
        site,
        before: { probing_depth: s0.probing_depth, gingival_margin: s0.gingival_margin, attachment_level: s0.attachment_level, bleeding: s0.bleeding },
        after: { probing_depth: s1.probing_depth, gingival_margin: s1.gingival_margin, attachment_level: s1.attachment_level, bleeding: s1.bleeding },
        probingDelta,
        attachmentDelta: delta(s1.attachment_level, s0.attachment_level),
        significant: probingDelta !== null && Math.abs(probingDelta) >= SIGNIFICANT_CHANGE_MM,
      });
    }
  }

  const significant = changes.filter((change) => change.significant);
  const keys: (keyof ExamSummary)[] = [
    "mean_probing_depth", "mean_attachment_level", "bleeding_pct", "plaque_pct", "deep_sites_pct",
  ];
  return {
    changes,
    significant,
    highlighted: new Set(significant.map((change) => change.tooth)),
    toothChanges,
    summaryDelta: Object.fromEntries(keys.map((key) => [key, delta(after.summary[key] as number | null, before.summary[key] as number | null)])),
  };
}
