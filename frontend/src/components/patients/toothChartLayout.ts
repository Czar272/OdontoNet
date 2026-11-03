/**
 * Disposición del odontograma en numeración FDI (ODON-260), vista del
 * profesional frente al paciente: arriba el maxilar superior (cuadrantes 1 y
 * 2), abajo el inferior (4 y 3); la derecha del paciente queda a la izquierda.
 */
export type Dentition = "permanent" | "deciduous";

const range = (quadrant: number, count: number, reverse: boolean) => {
  const teeth = Array.from({ length: count }, (_, i) => quadrant * 10 + i + 1);
  return reverse ? teeth.reverse() : teeth;
};

export interface ToothChartRows {
  upper: [number[], number[]];
  lower: [number[], number[]];
}

export const TOOTH_CHART: Record<Dentition, ToothChartRows> = {
  permanent: {
    upper: [range(1, 8, true), range(2, 8, false)],
    lower: [range(4, 8, true), range(3, 8, false)],
  },
  deciduous: {
    upper: [range(5, 5, true), range(6, 5, false)],
    lower: [range(8, 5, true), range(7, 5, false)],
  },
};

/** Dentición a mostrar para una pieza (temporal si es 51–85). */
export function dentitionOf(tooth: number | null): Dentition {
  return tooth !== null && tooth >= 51 ? "deciduous" : "permanent";
}
