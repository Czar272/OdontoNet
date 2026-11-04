import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { ClinicalVisit } from "../../types/clinicalVisit";
import type { PatientImage, PhotoConsent, PhotoConsentStatus } from "../../types/patientImage";
import ImagesCard from "./ImagesCard";
import { todayLocal } from "./imageUpload";

const consent = (version: number, granted: boolean, research_use = false): PhotoConsent => ({
  id: version, version, granted, research_use, signed_on: "2026-11-02", notes: version === 1 ? "Archivado en recepción" : null,
  recorded_by: { id: 1, name: "Dra. Ana" }, recorded_at: "2026-11-02T16:00:00Z",
});

const visit = (id: number, reason: string, voided = false): ClinicalVisit => ({
  id, patient_id: 5, revision: 1, visit_at: "2026-11-02T16:00:00Z", doctor: { id: 1, name: "Dra. Ana" }, reason,
  findings: null, diagnosis: null, procedures: null, instructions: null, next_visit_date: null,
  created_by: { id: 1, name: "Dra. Ana" }, created_at: "2026-11-02T16:00:00Z",
  updated_by: { id: 1, name: "Dra. Ana" }, updated_at: "2026-11-02T16:00:00Z",
  voided_at: voided ? "2026-11-02T17:00:00Z" : null, voided_by: null, void_reason: voided ? "x" : null,
});

const uploaded: PatientImage = {
  id: 7, patient_id: 5, clinical_visit: null, tooth: 36, content_type: "image/jpeg", size_bytes: 2048,
  width: 640, height: 480, consent_id: 1, uploaded_by: { id: 1, name: "Dra. Ana" }, uploaded_at: "2026-11-03T15:00:00Z",
};

let status: PhotoConsentStatus = { current: null, history: [] };
let gallery: PatientImage[] = [];

vi.mock("../../services/patientImageService", () => ({
  getPhotoConsent: vi.fn(async () => status),
  recordPhotoConsent: vi.fn(async (_p: number, data: object) => ({ ...consent(1, true), ...data })),
  uploadPatientImage: vi.fn(async (_p: number, _data: object, onProgress?: (n: number) => void) => {
    onProgress?.(40);
    onProgress?.(100);
    gallery = [uploaded];
    return uploaded;
  }),
  getPatientImages: vi.fn(async () => gallery),
  getPatientImageThumbnail: vi.fn(async () => new Blob(["x"], { type: "image/jpeg" })),
  getPatientImageFile: vi.fn(async () => new Blob(["x"], { type: "image/jpeg" })),
}));

vi.mock("../../services/clinicalVisitService", () => ({
  getVisits: vi.fn(async () => [visit(9, "Fotografías iniciales"), visit(8, "Consulta anulada", true)]),
}));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const service = await import("../../services/patientImageService");

beforeEach(() => {
  vi.clearAllMocks();
  status = { current: null, history: [] };
  gallery = [];
});

const granted = () => {
  status = { current: consent(2, true, true), history: [consent(2, true, true), consent(1, true)] };
};

const file = (name: string, size = 1024, type = "image/jpeg") =>
  new File([new Uint8Array(size)], name, { type });

const render = (props: Partial<{ canUpload: boolean; isArchived: boolean }> = {}) =>
  renderWithAuth(<ImagesCard patientId={5} canUpload isArchived={false} {...props} />, "doctor");

describe("ImagesCard", () => {
  it("sin consentimiento no permite subir y ofrece registrarlo", async () => {
    render();

    expect(await screen.findByText(/sin consentimiento registrado/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/fotografía \*/i)).not.toBeInTheDocument();
    expect(screen.getByText(/registra el consentimiento del paciente/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Registrar consentimiento" })).toBeInTheDocument();
  });

  it("registra el consentimiento con fecha de hoy y sin investigación por defecto", async () => {
    render();

    fireEvent.click(await screen.findByRole("button", { name: "Registrar consentimiento" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText(/fecha del documento/i)).toHaveValue(todayLocal());
    fireEvent.change(within(dialog).getByLabelText("Notas"), { target: { value: "  Carpeta 3  " } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Guardar consentimiento" }));

    await waitFor(() =>
      expect(service.recordPhotoConsent).toHaveBeenCalledWith(5, {
        granted: true, research_use: false, signed_on: todayLocal(), notes: "Carpeta 3",
      }),
    );
  });

  it("el uso en investigación solo se puede marcar si se autorizan las fotos", async () => {
    render();

    fireEvent.click(await screen.findByRole("button", { name: "Registrar consentimiento" }));
    const dialog = await screen.findByRole("dialog");
    const research = within(dialog).getByRole("checkbox", { name: /uso en investigación/i });
    expect(research).toBeEnabled();
    fireEvent.click(research);
    expect(research).toBeChecked();

    fireEvent.click(within(dialog).getByRole("radio", { name: /no autoriza/i }));
    expect(research).toBeDisabled();
    expect(research).not.toBeChecked();
  });

  it("muestra el consentimiento vigente, su historial y permite revocar", async () => {
    granted();
    render();

    expect(await screen.findByText(/consentimiento vigente/i)).toHaveTextContent("Incluye uso en investigación");
    fireEvent.click(screen.getByRole("button", { name: "Ver historial (2)" }));
    const history = screen.getByRole("list", { name: "Historial del consentimiento" });
    expect(within(history).getAllByRole("listitem")).toHaveLength(2);
    expect(within(history).getByText(/Archivado en recepción/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Revocar" }));
    const dialog = await screen.findByRole("dialog", { name: "Revocar consentimiento" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Guardar consentimiento" }));
    await waitFor(() =>
      expect(service.recordPhotoConsent).toHaveBeenCalledWith(5, expect.objectContaining({ granted: false, research_use: false })),
    );
  });

  it("con el consentimiento revocado no se puede subir", async () => {
    status = { current: consent(2, false), history: [consent(2, false), consent(1, true)] };
    render();

    expect(await screen.findByText(/consentimiento revocado/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/fotografía \*/i)).not.toBeInTheDocument();
  });

  it("rechaza en el navegador archivos con otro tipo o demasiado grandes", async () => {
    granted();
    render();

    const input = await screen.findByLabelText(/fotografía \*/i);
    fireEvent.change(input, { target: { files: [file("animacion.gif", 10, "image/gif")] } });
    expect(screen.getByRole("alert")).toHaveTextContent("JPEG, PNG o WebP");

    fireEvent.change(input, { target: { files: [file("grande.jpg", 10 * 1024 * 1024 + 1)] } });
    expect(screen.getByRole("alert")).toHaveTextContent("10 MB");
    expect(screen.getByRole("button", { name: /subir imagen/i })).toBeDisabled();
    expect(service.uploadPatientImage).not.toHaveBeenCalled();
  });

  it("sube con consulta y pieza y la foto aparece en la galería", async () => {
    granted();
    render();

    const input = await screen.findByLabelText(/fotografía \*/i);
    const photo = file("foto.jpg");
    fireEvent.change(input, { target: { files: [photo] } });
    expect(await screen.findByAltText("Vista previa de la fotografía elegida")).toBeInTheDocument();

    // Las consultas anuladas no se ofrecen.
    const select = screen.getByLabelText(/consulta \(opcional\)/i);
    await within(select).findByRole("option", { name: /Fotografías iniciales/ });
    expect(within(select).queryByRole("option", { name: /anulada/ })).not.toBeInTheDocument();
    fireEvent.change(select, { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Pieza 36" }));

    fireEvent.click(screen.getByRole("button", { name: /subir imagen/i }));

    await waitFor(() =>
      expect(service.uploadPatientImage).toHaveBeenCalledWith(
        5, { file: photo, clinical_visit_id: 9, tooth: 36 }, expect.any(Function),
      ),
    );
    const grid = await screen.findByRole("list", { name: "Fotografías del paciente" });
    expect(within(grid).getAllByRole("listitem")).toHaveLength(1);
    expect(within(grid).getByText(/pieza 36/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Galería (1)" })).toBeInTheDocument();
    // El formulario queda listo para otra foto.
    expect(screen.getByRole("button", { name: /subir imagen/i })).toBeDisabled();
  });

  it("el paciente archivado queda en solo lectura pero conserva la galería", async () => {
    granted();
    gallery = [uploaded];
    render({ isArchived: true });

    expect(await screen.findByRole("list", { name: "Fotografías del paciente" })).toBeInTheDocument();

    expect(await screen.findByText(/paciente archivado: no se pueden subir/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Revocar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Actualizar" })).not.toBeInTheDocument();
  });
});
