import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getAuditEvents } from "../../services/auditService";
import { getUsers } from "../../services/userService";
import { renderWithAuth } from "../../test/renderWithAuth";
import type { AuditEvent } from "../../types/audit";
import AuditPage from "./AuditPage";
import { actionLabel, entityLabel, fieldsLabel } from "./auditLabels";
import RequirePermission from "../../routes/RequirePermission";

function event(id: number, overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id,
    occurred_at: "2026-11-07T15:00:00+00:00",
    actor: { id: 1, name: "Dra. Ana Morales", role: "doctor" },
    action: "patient.updated",
    entity_type: "patient",
    entity_id: 40,
    patient_id: 40,
    fields: ["phone", "email"],
    ...overrides,
  };
}

vi.mock("../../services/auditService", () => ({
  getAuditEvents: vi.fn(async ({ cursor }: { cursor?: string | null }) =>
    cursor
      ? { items: [event(1, { action: "report.exported", entity_type: "report", entity_id: null, patient_id: null, fields: ["appointments"] })], next_cursor: null }
      : { items: [event(3), event(2, { action: "appointment.status_changed", entity_type: "appointment", entity_id: 9, fields: ["status"] })], next_cursor: "c2" },
  ),
}));
vi.mock("../../services/userService", () => ({
  getUsers: vi.fn(async () => [
    { id: 1, name: "Dra. Ana Morales", email: "a@x.com", role: "doctor", clinic_id: 1, is_active: true },
    { id: 2, name: "Recepción Uno", email: "r@x.com", role: "receptionist", clinic_id: 1, is_active: true },
  ]),
}));

beforeEach(() => vi.clearAllMocks());

describe("AuditPage", () => {
  it("lista los eventos con acción en español, registro, paciente y campos, y pagina", async () => {
    renderWithAuth(<AuditPage />, "admin");
    const table = await screen.findByRole("table", { name: "Eventos de auditoría" });
    expect(within(table).getByText("Editó un paciente")).toBeInTheDocument();
    expect(within(table).getByText("Paciente #40")).toBeInTheDocument();
    expect(within(table).getByText("teléfono, correo")).toBeInTheDocument();
    expect(within(table).getAllByRole("link", { name: "Ver paciente" })[0]).toHaveAttribute("href", "/patients/40");

    fireEvent.click(screen.getByRole("button", { name: "Cargar más" }));
    expect(await within(table).findByText("Exportó un reporte (CSV)")).toBeInTheDocument();
    expect(vi.mocked(getAuditEvents).mock.lastCall?.[0].cursor).toBe("c2");
    expect(screen.queryByRole("button", { name: "Cargar más" })).not.toBeInTheDocument();
  });

  it("administración filtra por usuario y acción", async () => {
    renderWithAuth(<AuditPage />, "admin");
    await screen.findByRole("table", { name: "Eventos de auditoría" });
    await screen.findByRole("option", { name: "Recepción Uno" });
    fireEvent.change(screen.getByLabelText("Usuario"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Acción"), { target: { value: "report.exported" } });
    await waitFor(() =>
      expect(vi.mocked(getAuditEvents).mock.lastCall?.[0]).toMatchObject({ actorUserId: 2, action: "report.exported" }),
    );
  });

  it("un doctor ve sus acciones sin filtro de usuario", async () => {
    renderWithAuth(<AuditPage />, "doctor");
    await screen.findByRole("table", { name: "Eventos de auditoría" });
    expect(screen.queryByLabelText("Usuario")).not.toBeInTheDocument();
    expect(getUsers).not.toHaveBeenCalled();
    expect(screen.getByText(/Tus cambios y exportaciones/)).toBeInTheDocument();
  });

  it("valida el rango de fechas", async () => {
    renderWithAuth(<AuditPage />, "admin");
    await screen.findByRole("table", { name: "Eventos de auditoría" });
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-11-10" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-11-01" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("anterior a la inicial");
  });
});

describe("acceso por rol", () => {
  it("recepción no entra a la pantalla de auditoría", () => {
    renderWithAuth(
      <RequirePermission permission="audit:view">
        <AuditPage />
      </RequirePermission>,
      "receptionist",
    );
    expect(screen.getByRole("heading", { name: "Acceso denegado" })).toBeInTheDocument();
    expect(getAuditEvents).not.toHaveBeenCalled();
  });
});

describe("auditLabels", () => {
  it("traduce acciones y entidades, y deja tal cual lo desconocido", () => {
    expect(actionLabel("clinical_visit.voided")).toBe("Anuló una consulta");
    expect(actionLabel("algo.nuevo")).toBe("algo.nuevo");
    expect(entityLabel("periodontal_exam", 5)).toBe("Periodontograma #5");
    expect(entityLabel("report", null)).toBe("Reporte");
    expect(fieldsLabel(["void_reason", "campo_nuevo"])).toBe("motivo de anulación, campo_nuevo");
  });
});
