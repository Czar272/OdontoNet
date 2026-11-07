import type { ToothData } from "../../types/periodontal";
import {
  CEJ_Y,
  FACE_HEIGHT,
  SITE_X,
  TOOTH_WIDTH,
  apicalOf,
  crownPath,
  displayEntrances,
  displaySites,
  MM,
  implantPath,
  marginY,
  pocketY,
  toothPath,
  type Arch,
  type Face,
} from "./periodontalChart";

interface ToothFaceProps {
  arch: Arch;
  face: Face;
  /** Piezas de la arcada en orden de pantalla. */
  teeth: ToothData[];
  /** Piezas resaltadas (p. ej. cambios al comparar). */
  highlighted?: Set<number>;
}

const COLORS = {
  margin: "#dc2626", // margen gingival
  pocket: "#2563eb", // fondo de la bolsa
  pocketFill: "rgba(37, 99, 235, 0.18)",
  cej: "#94a3b8",
};

/**
 * Dibujo de una cara de una arcada (ODON-186). Siluetas propias de OdontoNet;
 * la línea roja es el margen gingival y la azul el fondo de la bolsa, ambas
 * recalculadas a cada valor que se escribe. Lo sombreado es la bolsa.
 */
export default function ToothFace({ arch, face, teeth, highlighted }: ToothFaceProps) {
  const apical = apicalOf(arch, face);
  const width = teeth.length * TOOTH_WIDTH;
  const faceName =
    face === "buccal" ? "vestibular" : arch === "upper" ? "palatina" : "lingual";

  return (
    <svg
      role="img"
      aria-label={`Dibujo de la cara ${faceName} de la arcada ${arch === "upper" ? "superior" : "inferior"}`}
      viewBox={`0 0 ${width} ${FACE_HEIGHT}`}
      width={width}
      height={FACE_HEIGHT}
      className="block"
    >
      {/* Referencias cada 2 mm, como una regla de sonda. */}
      {Array.from({ length: 15 }, (_, i) => CEJ_Y + apical * (i + 1) * 2 * MM).map((y) => (
        <line key={y} x1={0} x2={width} y1={y} y2={y} stroke="#e2e8f0" strokeWidth={0.5} />
      ))}

      {teeth.map((tooth, index) => {
        const x0 = index * TOOTH_WIDTH;
        const sites = displaySites(tooth.tooth, face);
        const data = sites.map((site) => tooth.sites[site]);
        const points = (fn: (i: number) => number) =>
          SITE_X.map((x, i) => `${x0 + x},${fn(i)}`).join(" ");
        const margin = points((i) => marginY(apical, data[i].gingival_margin));
        const pocket = points((i) => pocketY(apical, data[i]));
        const hasData = data.some((site) => site.probing_depth !== null || site.gingival_margin !== null);
        const entrances = displayEntrances(tooth.tooth, face);

        return (
          <g key={tooth.tooth} data-tooth={tooth.tooth}>
            {highlighted?.has(tooth.tooth) && (
              <rect x={x0 + 1} y={2} width={TOOTH_WIDTH - 2} height={FACE_HEIGHT - 4} rx={6}
                fill="rgba(245, 158, 11, 0.12)" stroke="#f59e0b" strokeWidth={1} />
            )}
            <g transform={`translate(${x0} 0)`} opacity={tooth.missing ? 0.25 : 1}>
              {tooth.implant ? (
                <>
                  <path d={implantPath(apical)} fill="#cbd5e1" stroke="#475569" strokeWidth={1} />
                  <path d={crownPath(tooth.tooth, apical)} fill="#ffffff" stroke="#64748b" strokeWidth={1.2} />
                </>
              ) : (
                <path d={toothPath(tooth.tooth, apical)} fill="#ffffff" stroke="#64748b" strokeWidth={1.2} />
              )}
              {tooth.missing && (
                <path d={`M 8 ${CEJ_Y - 30} L ${TOOTH_WIDTH - 8} ${CEJ_Y + 30} M ${TOOTH_WIDTH - 8} ${CEJ_Y - 30} L 8 ${CEJ_Y + 30}`}
                  stroke="#64748b" strokeWidth={1.5} />
              )}
            </g>

            {!tooth.missing && (
              <>
                <line x1={x0} x2={x0 + TOOTH_WIDTH} y1={CEJ_Y} y2={CEJ_Y} stroke={COLORS.cej} strokeDasharray="2 2" strokeWidth={0.8} />
                {hasData && (
                  <>
                    <polygon
                      points={`${margin} ${pocket.split(" ").reverse().join(" ")}`}
                      fill={COLORS.pocketFill}
                      data-testid={`pocket-${face}-${tooth.tooth}`}
                    />
                    <polyline points={margin} fill="none" stroke={COLORS.margin} strokeWidth={1.8}
                      data-testid={`margin-${face}-${tooth.tooth}`} />
                    <polyline points={pocket} fill="none" stroke={COLORS.pocket} strokeWidth={1.8}
                      data-testid={`depth-${face}-${tooth.tooth}`} />
                  </>
                )}
                {/* Sangrado, supuración y placa como puntos junto al margen. */}
                {data.map((site, i) => {
                  const x = x0 + SITE_X[i];
                  const y = CEJ_Y - apical * 46;
                  return (
                    <g key={sites[i]}>
                      {site.bleeding && <circle cx={x} cy={y} r={3.2} fill="#dc2626" />}
                      {site.suppuration && <circle cx={x} cy={y - apical * 8} r={3.2} fill="#eab308" />}
                      {site.plaque && <circle cx={x} cy={y - apical * 16} r={3.2} fill="#0ea5e9" />}
                    </g>
                  );
                })}
                {entrances.map((entrance, i) => {
                  const grade = tooth.furcation[entrance];
                  if (!grade) return null;
                  const x = x0 + TOOTH_WIDTH / 2 + (entrances.length > 1 ? (i === 0 ? -9 : 9) : 0);
                  const y = CEJ_Y + apical * 22;
                  // Triángulo abierto (I), medio lleno (II) o lleno (III).
                  return (
                    <path key={entrance}
                      d={`M ${x - 5} ${y + apical * 4} L ${x} ${y - apical * 5} L ${x + 5} ${y + apical * 4} Z`}
                      fill={grade === 3 ? "#0f172a" : grade === 2 ? "#94a3b8" : "#ffffff"}
                      stroke="#0f172a" strokeWidth={1}
                      data-testid={`furcation-${entrance}-${tooth.tooth}`} />
                  );
                })}
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}
