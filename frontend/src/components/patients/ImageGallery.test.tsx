import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { PatientImage } from "../../types/patientImage";
import ImageGallery from "./ImageGallery";
import { GALLERY_PAGE_SIZE } from "./imageUpload";

const image = (id: number, extra: Partial<PatientImage> = {}): PatientImage => ({
  id, patient_id: 5, clinical_visit: null, tooth: null, content_type: "image/jpeg", size_bytes: 2048,
  width: 640, height: 480, consent_id: 1, uploaded_by: { id: 1, name: "Dra. Ana" },
  uploaded_at: `2026-11-0${(id % 9) + 1}T15:00:00Z`, ...extra,
});

let gallery: PatientImage[] = [];

vi.mock("../../services/patientImageService", () => ({
  getPatientImages: vi.fn(async () => gallery),
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
    renderWithAuth(<ImageGallery patientId={5} />, "doctor");

    expect(await screen.findByText("Aún no hay fotografías de este paciente.")).toBeInTheDocument();
  });

  it("muestra miniaturas pedidas con el token, con fecha, pieza y autor", async () => {
    gallery = [image(2, { tooth: 36 }), image(1, { uploaded_by: { id: 2, name: "Dr. Luis" } })];
    renderWithAuth(<ImageGallery patientId={5} />, "doctor");

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
    renderWithAuth(<ImageGallery patientId={5} />, "doctor");

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
    renderWithAuth(<ImageGallery patientId={5} />, "doctor");

    const grid = await screen.findByRole("list", { name: "Fotografías del paciente" });
    fireEvent.click(within(within(grid).getAllByRole("listitem")[0]).getByRole("button"));

    const dialog = await screen.findByRole("dialog", { name: "Fotografía 1 de 2" });
    await waitFor(() => expect(service.getPatientImageFile).toHaveBeenCalledWith(5, 2));
    expect(await within(dialog).findByAltText(/Fotografía clínica del/)).toHaveAttribute("src", expect.stringMatching(/^data:/));
    expect(within(dialog).getByText(/· Control/)).toBeInTheDocument();
    expect(within(dialog).getByText("36")).toBeInTheDocument();
    expect(within(dialog).getByText("640 × 480 px · 2 KB")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /más reciente/i })).toBeDisabled();

    fireEvent.click(within(dialog).getByRole("button", { name: /más antigua/i }));
    expect(await screen.findByRole("dialog", { name: "Fotografía 2 de 2" })).toBeInTheDocument();
    await waitFor(() => expect(service.getPatientImageFile).toHaveBeenCalledWith(5, 1));
    expect(screen.getByText("Sin consulta")).toBeInTheDocument();
    expect(screen.getByText("Sin pieza")).toBeInTheDocument();
  });
});
