import { describe, expect, it } from "vitest";

/**
 * Windows y macOS no distinguen mayúsculas: `./ToothChart` podría resolver a
 * `toothChart.ts`. Esta prueba falla si dos módulos de una misma carpeta solo
 * difieren en mayúsculas (ignorando la extensión y el sufijo .test).
 */
const FILES = Object.keys(import.meta.glob("/src/**/*.{ts,tsx,css}"));

function collisions(paths: string[]): string[] {
  const seen = new Map<string, string>();
  const found: string[] = [];
  for (const path of paths) {
    const slash = path.lastIndexOf("/");
    const dir = path.slice(0, slash);
    const base = path
      .slice(slash + 1)
      .replace(/\.[^.]+$/, "")
      .replace(/\.test$/, "");
    const key = `${dir}/${base}`.toLowerCase();
    const previous = seen.get(key);
    if (previous !== undefined && previous !== `${dir}/${base}`) {
      found.push(`${path} ↔ ${previous}`);
    }
    seen.set(key, `${dir}/${base}`);
  }
  return found;
}

describe("nombres de archivo", () => {
  it("encuentra los módulos de src", () => {
    expect(FILES.length).toBeGreaterThan(10);
  });

  it("no hay módulos que solo difieran en mayúsculas", () => {
    expect(collisions(FILES)).toEqual([]);
  });
});
