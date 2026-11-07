import type { PeriodontalExam, SiteCode, ToothData } from "../../types/periodontal";
import { SITES, chartFromExam, emptyFurcation, emptySite } from "./periodontalChart";

/** Qué se copia del examen anterior al registrar uno nuevo (ODON-190). */
export interface CopyOptions {
  /** Piezas ausentes e implantes. */
  dentalStatus: boolean;
  mobilityAndFurcation: boolean;
  /** Sondajes y márgenes gingivales. */
  measurements: boolean;
  /** Sangrado, supuración y placa. */
  indicators: boolean;
}

export const DEFAULT_COPY: CopyOptions = {
  dentalStatus: true,
  mobilityAndFurcation: false,
  measurements: false,
  indicators: false,
};

export const COPY_LABELS: Record<keyof CopyOptions, string> = {
  dentalStatus: "Estado dental (piezas ausentes e implantes)",
  mobilityAndFurcation: "Movilidad y furcaciones",
  measurements: "Sondajes y márgenes gingivales",
  indicators: "Sangrado, supuración y placa",
};

/** Contenido inicial de un examen nuevo copiando lo elegido del anterior. Las notas no se copian. */
export function copyChart(previous: PeriodontalExam, options: CopyOptions): ToothData[] {
  return chartFromExam(previous).map((tooth) => {
    const missing = options.dentalStatus && tooth.missing;
    const implant = options.dentalStatus && tooth.implant;
    return {
      tooth: tooth.tooth,
      missing,
      implant,
      mobility: !missing && options.mobilityAndFurcation ? tooth.mobility : null,
      furcation: !missing && !implant && options.mobilityAndFurcation ? { ...tooth.furcation } : emptyFurcation(),
      note: null,
      sites: Object.fromEntries(
        SITES.map((site) => {
          const source = tooth.sites[site];
          const empty = emptySite();
          if (missing) return [site, empty];
          return [
            site,
            {
              probing_depth: options.measurements ? source.probing_depth : null,
              gingival_margin: options.measurements ? source.gingival_margin : null,
              bleeding: options.indicators ? source.bleeding : false,
              suppuration: options.indicators ? source.suppuration : false,
              plaque: options.indicators ? source.plaque : false,
            },
          ];
        }),
      ) as Record<SiteCode, ToothData["sites"][SiteCode]>,
    };
  });
}
