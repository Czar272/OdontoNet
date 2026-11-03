import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { TimelineEvent } from "../../types/timeline";
import TimelineCard from "./TimelineCard";

const event = (id: string, type: TimelineEvent["type"], title: string, extra: Partial<TimelineEvent> = {}): TimelineEvent => ({
  id, type, action: "attended", occurred_at: "2026-11-02T16:00:00Z", title, detail: null,
  actor: { id: 1, name: "Dra. Ana" }, ref_id: 1, voided: false, ...extra,
});

const page1 = {
  items: [
    event("visit.attended:2", "visit", "Consulta: Evaluación", { detail: "Gingivitis" }),
    event("treatment.status:5", "treatment", "Tratamiento completado: Raspado (pieza 36)", { action: "completed" }),
    event("visit.attended:1", "visit", "Consulta: Duplicada", { voided: true }),
  ],
  next_cursor: "cursor-2",
};
const page2 = {
  items: [event("appointment.completed:3", "appointment", "Cita atendida: Limpieza", { action: "completed" })],
  next_cursor: null,
};

vi.mock("../../services/timelineService", () => ({
  getTimeline: vi.fn(async (_patient: number, params: { cursor?: string | null }) => (params.cursor ? page2 : page1)),
}));

const { getTimeline } = await import("../../services/timelineService");

beforeEach(() => vi.clearAllMocks());

describe("TimelineCard", () => {
  it("muestra los eventos con fecha, autor y detalle", async () => {
    renderWithAuth(<TimelineCard patientId={5} />, "doctor");

    const list = await screen.findByRole("list", { name: "Historial cronológico" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(within(list).getByText("Gingivitis")).toBeInTheDocument();
    expect(within(list).getByText("Tratamiento completado: Raspado (pieza 36)")).toBeInTheDocument();
    expect(within(list).getAllByText(/Dra\. Ana/)).toHaveLength(3);
  });

  it("marca las consultas anuladas", async () => {
    renderWithAuth(<TimelineCard patientId={5} />, "doctor");

    const title = await screen.findByText("Consulta: Duplicada");
    expect(title).toHaveClass("line-through");
    expect(title.closest("li")).toHaveTextContent("anulada");
  });

  it("«Ver más» trae la página siguiente con el cursor", async () => {
    renderWithAuth(<TimelineCard patientId={5} />, "doctor");

    fireEvent.click(await screen.findByRole("button", { name: "Ver más" }));

    expect(await screen.findByText("Cita atendida: Limpieza")).toBeInTheDocument();
    expect(getTimeline).toHaveBeenLastCalledWith(5, expect.objectContaining({ cursor: "cursor-2" }));
    expect(screen.queryByRole("button", { name: "Ver más" })).not.toBeInTheDocument();
  });

  it("filtra por tipo de evento", async () => {
    renderWithAuth(<TimelineCard patientId={5} />, "doctor");
    await screen.findByText("Consulta: Evaluación");

    fireEvent.click(screen.getByLabelText("Citas"));

    await waitFor(() =>
      expect(getTimeline).toHaveBeenLastCalledWith(5, expect.objectContaining({ types: ["visit", "treatment", "medical_history"] })),
    );
  });

  it("sin tipos elegidos no consulta y lo indica", async () => {
    renderWithAuth(<TimelineCard patientId={5} />, "doctor");
    await screen.findByText("Consulta: Evaluación");

    for (const label of ["Consultas", "Tratamientos", "Historia médica", "Citas"]) {
      fireEvent.click(screen.getByLabelText(label));
    }

    expect(await screen.findByText("Elige al menos un tipo de evento.")).toBeInTheDocument();
    const typesSent = vi.mocked(getTimeline).mock.calls.map(([, params]) => params?.types ?? []);
    expect(typesSent.every((types) => types.length > 0)).toBe(true);
  });

  it("paciente sin eventos", async () => {
    vi.mocked(getTimeline).mockResolvedValueOnce({ items: [], next_cursor: null });
    renderWithAuth(<TimelineCard patientId={5} />, "doctor");

    expect(await screen.findByText(/Todavía no hay eventos/)).toBeInTheDocument();
  });
});
