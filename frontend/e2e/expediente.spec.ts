import { expect, test } from "@playwright/test";

import {
  DOCTORA_NORTE,
  USUARIOS,
  crearPacienteApi,
  iniciarSesion,
  sufijoUnico,
} from "./support/helpers";

test.describe("Expediente clínico", () => {
  test("un doctor registra una consulta y un tratamiento y los ve en el historial", async ({ page }, testInfo) => {
    const sufijo = sufijoUnico(testInfo);
    const motivo = `Dolor molar ${sufijo}`;
    const procedimiento = `Resina ${sufijo}`;
    const pacienteId = await crearPacienteApi(USUARIOS.doctorNorte, {
      first_name: "Paciente",
      last_name: `Expediente ${sufijo}`,
    });

    await iniciarSesion(page, USUARIOS.doctorNorte);
    await page.goto(`/patients/${pacienteId}`);
    const pestanas = page.getByRole("tablist", { name: "Secciones del expediente" });

    // Consulta clínica.
    await pestanas.getByRole("tab", { name: "Consultas" }).click();
    await expect(page.getByText("Este paciente aún no tiene consultas registradas.")).toBeVisible();
    await page.getByRole("button", { name: "Nueva consulta" }).click();

    const consulta = page.getByRole("form", { name: "Nueva consulta" });
    // El doctor propuesto es el propio perfil del usuario.
    await expect(consulta.getByLabel("Doctor *")).toHaveValue(/\d+/);
    await expect(consulta.getByLabel("Doctor *").locator("option:checked")).toHaveText(DOCTORA_NORTE);
    await consulta.getByLabel("Motivo de la consulta *").fill(motivo);
    await consulta.getByLabel("Hallazgos / examen").fill("Caries oclusal en pieza 36.");
    await consulta.getByLabel("Indicaciones").fill("Control en un mes.");
    await consulta.getByRole("button", { name: "Registrar consulta" }).click();

    await expect(page.getByText("Consulta registrada")).toBeVisible();
    const listaConsultas = page.getByRole("list", { name: "Consultas" });
    await expect(listaConsultas.getByRole("listitem")).toHaveCount(1);
    await expect(listaConsultas).toContainText(motivo);
    await expect(listaConsultas).toContainText("Caries oclusal en pieza 36.");

    // Tratamiento propuesto.
    await pestanas.getByRole("tab", { name: "Tratamientos" }).click();
    await page.getByRole("button", { name: "Nuevo tratamiento" }).click();
    const tratamiento = page.getByRole("form", { name: "Nuevo tratamiento" });
    await tratamiento.getByLabel("Procedimiento *").fill(procedimiento);
    await tratamiento.getByLabel("Pieza dental (FDI)").fill("36");
    await tratamiento.getByRole("button", { name: "Registrar tratamiento" }).click();
    await expect(page.getByRole("list", { name: "Tratamientos pendientes" })).toContainText(procedimiento);

    // Historial cronológico con ambos eventos.
    await pestanas.getByRole("tab", { name: "Historial" }).click();
    const historial = page.getByRole("list", { name: "Historial cronológico" });
    await expect(historial.getByText(`Consulta: ${motivo}`)).toBeVisible();
    await expect(historial.getByText(new RegExp(`^Tratamiento propuesto: ${procedimiento}`))).toBeVisible();
  });
});
