import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { PatientImage } from "../../types/patientImage";
import ImageGallery from "./ImageGallery";
import { GALLERY_PAGE_SIZE } from "./imageUpload";

const image = (id: number, extra: Partial<PatientImage> = {}): PatientImage => ({
  id, patient_id: 5, clinical_visit: null, tooth: null, origin: "phone", view: null, taken_on: null, revision: 1,
  content_type: "image/jpeg", size_bytes: 2048, width: 640, height: 480, consent_id: 1,
  uploaded_by: { id: 1, name: "Dra. Ana" }, uploaded_at: `2026-11-0${(id % 9) + 1}T15:00:00Z`,
  voided_at: null, voided_by: null, void_reason: null, ...extra,
});

let gallery: PatientImage[] = [];

vi.mock("../../services/clinicalVisitService", () => ({ getVisits: vi.fn(async () => []) }));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

vi.mock("../../services/patientImageService", () => ({
  getPatientImages: vi.fn(async () => gallery),
  updatePatientImage: vi.fn(async (_p: number, id: number, data: object) => ({ ...image(id), ...data, revision: 2 })),
  voidPatientImage: vi.fn(async (_p: number, id: number, reason: string) => ({ ...image(id), void_reason: reason })),
  getPatientImageRevisions: vi.fn(async () => [
    { revision: 2, origin: "intraoral_camera", view: "frontal", taken_on: "2026-11-01", clinical_visit_id: null, tooth: 16,
      edited_by: { id: 1, name: "Dra. Ana" }, edited_at: "2026-11-04T10:00:00Z" },
    { revision: 1, origin: null, view: null, taken_on: null, clinical_visit_id: null, tooth: null,
      edited_by: { id: 1, name: "Dra. Ana" }, edited_at: "2026-11-03T10:00:00Z" },
  ]),
  getPatientImageAccessLog: vi.fn(async () => [{ user: { id: 3, name: "Admin Clínica" }, accessed_at: "2026-11-04T11:00:00Z" }]),
  getPatientImageThumbnail: vi.fn(async (_p: number, id: number) => new Blob([`miniatura-${id}`], { type: "image/jpeg" })),
  getPatientImageFile: vi.fn(async (_p: number, id: number) => new Blob([`original-${id}`], { type: "image/jpeg" })),
}));

const service = await import("../../services/patientImageService");

beforeEach(() => {
  vi.clearAllMocks();
  gallery = [];
});

describe("ImageGallery", () => {
  it("indica cuando no hay fotografías", async () => {
    renderWithAuth(<ImageGallery patientId={5} canManage isArchived={false} />, "doctor");

    expect(await screen.findByText("Aún no hay fotografías de este paciente.")).toBeInTheDocument();
  });

  it("muestra miniaturas pedidas con el token, con fecha, pieza y autor", async () => {
    gallery = [image(2, { tooth: 36 }), image(1, { uploaded_by: { id: 2, name: "Dr. Luis" } })];
    renderWithAuth(<ImageGallery patientId={5} canManage isArchived={false} />, "doctor");

    const grid = await screen.findByRole("list", { name: "Fotografías del paciente" });
    const items = within(grid).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText(/pieza 36/)).toBeInTheDocument();
    expect(within(items[1]).getByText("Dr. Luis")).toBeInTheDocument();
    await waitFor(() => expect(service.getPatientImageThumbnail).toHaveBeenCalledTimes(2));
    expect(service.getPatientImageFile).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(items[0].querySelector("img")).toHaveAttribute("src", expect.stringMatching(/^data:image\/jpeg/)),
    );
  });

  it("pide las miniaturas por tandas con «Ver más»", async () => {
    gallery = Array.from({ length: GALLERY_PAGE_SIZE + 3 }, (_, i) => image(100 - i));
    renderWithAuth(<ImageGallery patientId={5} canManage isArchived={false} />, "doctor");

    const grid = await screen.findByRole("list", { name: "Fotografías del paciente" });
    expect(within(grid).getAllByRole("listitem")).toHaveLength(GALLERY_PAGE_SIZE);
    expect(screen.getByRole("heading", { name: `Galería (${GALLERY_PAGE_SIZE + 3})` })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Ver más (3)" }));
    expect(within(grid).getAllByRole("listitem")).toHaveLength(GALLERY_PAGE_SIZE + 3);
    expect(screen.queryByRole("button", { name: /ver más/i })).not.toBeInTheDocument();
  });

  it("abre el visor con el original y sus datos, y navega entre fotos", async () => {
    gallery = [
      image(2, { tooth: 36, clinical_visit: { id: 9, visit_at: "2026-11-02T16:00:00Z", reason: "Control", voided: false } }),
      image(1),
    ];
    renderWithAuth(<ImageGallery patientId={5} canManage isArchived={false} />, "doctor");

    const grid = await screen.findByRole("list", { name: "Fotografías del paciente" });
    fireEvent.click(within(within(grid).getAllByRole("listitem")[0]).getByRole("button"));

    const dialog = await screen.findByRole("dialog", { name: "Fotografía 1 de 2" });
    await waitFor(() => expect(service.getPatientImageFile).toHaveBeenCalledWith(5, 2));
    expect(await within(dialog).findByAltText(/Fotografía clínica del/)).toHaveAttribute("src", expect.stringMatching(/^data:/));
    expect(within(dialog).getByText(/· Control/)).toBeInTheDocument();
    expect(within(dialog).getByText("36")).toBeInTheDocument();
    expect(within(dialog).getByText("640 × 480 px · 2 KB")).toBeInTheDocument();
    expect(within(dialog).getByText("Celular")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /más reciente/i })).toBeDisabled();

    fireEvent.click(within(dialog).getByRole("button", { name: /más antigua/i }));
    expect(await screen.findByRole("dialog", { name: "Fotografía 2 de 2" })).toBeInTheDocument();
    await waitFor(() => expect(service.getPatientImageFile).toHaveBeenCalledWith(5, 1));
    expect(screen.getByText("Sin consulta")).toBeInTheDocument();
    expect(screen.getByText("Sin pieza")).toBeInTheDocument();
  });

  const openFirst = async () => {
    const grid = await screen.findByRole("list", { name: "Fotografías del paciente" });
    fireEvent.click(within(within(grid).getAllByRole("listitem")[0]).getByRole("button"));
    return screen.findByRole("dialog");
  };

  it("oculta las anuladas salvo que se pidan", async () => {
    gallery = [image(2), image(1, { voided_at: "2026-11-04T10:00:00Z", voided_by: { id: 1, name: "Dra. Ana" }, void_reason: "Paciente equivocado" })];
    renderWithAuth(<ImageGallery patientId={5} canManage isArchived={false} />, "doctor");

    const grid = await screen.findByRole("list", { name: "Fotografías del paciente" });
    expect(within(grid).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "Galería (1)" })).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Mostrar anuladas (1)"));
    expect(within(grid).getAllByRole("listitem")).toHaveLength(2);
    expect(within(grid).getByText("Anulada")).toBeInTheDocument();

    fireEvent.click(within(grid).getByRole("button", { name: /anulada/ }));
    const banner = await screen.findByText(/Motivo: Paciente equivocado/);
    // Sin doble punto tras «a. m.» / «p. m.».
    expect(banner.textContent).not.toMatch(/\.\./);
    expect(screen.queryByRole("button", { name: "Corregir datos" })).not.toBeInTheDocument();
  });

  it("quien la subió corrige los datos con la revisión vigente", async () => {
    gallery = [image(2, { tooth: 36, view: "frontal", revision: 3 })];
    renderWithAuth(<ImageGallery patientId={5} canManage isArchived={false} />, "doctor");

    const dialog = await openFirst();
    fireEvent.click(within(dialog).getByRole("button", { name: "Corregir datos" }));
    const form = within(dialog).getByRole("form", { name: "Corregir datos de la fotografía" });
    expect(within(form).getByLabelText(/origen/i)).toHaveValue("phone");
    fireEvent.change(within(form).getByLabelText(/origen/i), { target: { value: "intraoral_camera" } });
    fireEvent.change(within(form).getByLabelText("Fecha de toma"), { target: { value: "2026-11-01" } });
    fireEvent.click(within(form).getByRole("button", { name: "Pieza 36" })); // la quita
    fireEvent.click(within(form).getByRole("button", { name: "Guardar corrección" }));

    await waitFor(() =>
      expect(service.updatePatientImage).toHaveBeenCalledWith(5, 2, {
        base_revision: 3, origin: "intraoral_camera", view: "frontal", taken_on: "2026-11-01",
        clinical_visit_id: null, tooth: null,
      }),
    );
  });

  it("anula con motivo", async () => {
    gallery = [image(2)];
    renderWithAuth(<ImageGallery patientId={5} canManage isArchived={false} />, "doctor");

    const dialog = await openFirst();
    fireEvent.click(within(dialog).getByRole("button", { name: /anular/i }));
    const form = within(dialog).getByRole("form", { name: "Anular fotografía" });
    const submit = within(form).getByRole("button", { name: "Anular fotografía" });
    expect(submit).toBeDisabled();
    fireEvent.change(within(form).getByLabelText(/motivo/i), { target: { value: "  Foto de otro paciente " } });
    fireEvent.click(submit);

    await waitFor(() => expect(service.voidPatientImage).toHaveBeenCalledWith(5, 2, "Foto de otro paciente"));
  });

  it("un doctor no modifica fotos de otro; administración sí", async () => {
    gallery = [image(2, { uploaded_by: { id: 2, name: "Dr. Luis" } })];
    const { unmount } = renderWithAuth(<ImageGallery patientId={5} canManage isArchived={false} />, "doctor");
    let dialog = await openFirst();
    expect(within(dialog).queryByRole("button", { name: "Corregir datos" })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Accesos" })).not.toBeInTheDocument();
    unmount();

    renderWithAuth(<ImageGallery patientId={5} canManage isArchived={false} />, "admin");
    dialog = await openFirst();
    expect(within(dialog).getByRole("button", { name: "Corregir datos" })).toBeInTheDocument();
  });

  it("paciente archivado: sin corregir ni anular", async () => {
    gallery = [image(2)];
    renderWithAuth(<ImageGallery patientId={5} canManage isArchived />, "doctor");

    const dialog = await openFirst();
    expect(within(dialog).queryByRole("button", { name: "Corregir datos" })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /anular/i })).not.toBeInTheDocument();
  });

  it("muestra el historial de cambios y, a administración, los accesos", async () => {
    gallery = [image(2)];
    renderWithAuth(<ImageGallery patientId={5} canManage isArchived={false} />, "admin");

    const dialog = await openFirst();
    fireEvent.click(within(dialog).getByRole("button", { name: /historial de cambios/i }));
    const history = await within(dialog).findByRole("list", { name: "Historial de cambios" });
    expect(within(history).getAllByRole("listitem")).toHaveLength(2);
    expect(within(history).getByText(/Cámara intraoral · Frontal · tomada el .* · pieza 16/)).toBeInTheDocument();
    expect(within(history).getByText("Origen sin registrar")).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: /accesos/i }));
    const access = await within(dialog).findByRole("list", { name: "Accesos al original" });
    expect(within(access).getByText(/Admin Clínica/)).toBeInTheDocument();
  });
});
