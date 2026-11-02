import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.hoisted(() => vi.fn(async () => ({ data: { items: [], total: 0, page: 1, page_size: 20 } })));

vi.mock("./api", () => ({ default: { get } }));

const { getPatients } = await import("./patientService");

beforeEach(() => get.mockClear());

describe("getPatients", () => {
  it("sin filtros no envía parámetros: el backend devuelve activos, página 1", async () => {
    await getPatients();

    expect(get).toHaveBeenCalledWith("/patients/", { params: {} });
  });

  it("traduce los filtros a los parámetros de la API y omite los vacíos", async () => {
    await getPatients({ archived: true, search: "  perez ", doctorId: 3, page: 2, pageSize: 20 });
    await getPatients({ archived: false, search: "   ", doctorId: undefined });

    expect(get).toHaveBeenNthCalledWith(1, "/patients/", {
      params: { archived: true, q: "perez", doctor_id: 3, page: 2, page_size: 20 },
    });
    expect(get).toHaveBeenNthCalledWith(2, "/patients/", { params: {} });
  });
});
