import { expect, test } from "@playwright/test";

import { USUARIOS, crearPacienteApi, iniciarSesion, sufijoUnico } from "./support/helpers";

test.describe("Errores y estados vacíos", () => {
  test("un paciente nuevo muestra los estados vacíos del expediente", async ({ page }, testInfo) => {
    const pacienteId = await crearPacienteApi(USUARIOS.doctorNorte, {
      first_name: "Paciente",
      last_name: `Vacio ${sufijoUnico(testInfo)}`,
    });

    await iniciarSesion(page, USUARIOS.doctorNorte);

    await page.goto(`/patients/${pacienteId}?tab=consultas`);
    await expect(page.getByText("Este paciente aún no tiene consultas registradas.")).toBeVisible();

    await page.getByRole("tab", { name: "Tratamientos" }).click();
    await expect(page.getByText("Este paciente aún no tiene tratamientos registrados.")).toBeVisible();

    await page.getByRole("tab", { name: "Historial" }).click();
    await expect(
      page.getByText("Todavía no hay eventos en el historial de este paciente."),
    ).toBeVisible();
  });

  test("una búsqueda sin resultados muestra su mensaje", async ({ page }, testInfo) => {
    await iniciarSesion(page, USUARIOS.adminNorte);
    await page.goto("/patients");

    await page.getByLabel("Buscar pacientes").fill(`Inexistente ${sufijoUnico(testInfo)}`);

    await expect(page.getByText("No hay pacientes que coincidan con la búsqueda.")).toBeVisible();
    await page.getByRole("button", { name: "Limpiar filtros" }).click();
    await expect(page.getByLabel("Buscar pacientes")).toHaveValue("");
    // Sin filtro vuelven los pacientes del seed.
    await expect(page.getByRole("navigation", { name: "Paginación de pacientes" })).toBeVisible();
  });

  test("recepción ve «Acceso denegado» en rutas sin permiso", async ({ page }) => {
    await iniciarSesion(page, USUARIOS.recepcionNorte);

    for (const ruta of ["/audit", "/users"]) {
      await page.goto(ruta);
      await expect(page.getByRole("heading", { level: 1, name: "Acceso denegado" })).toBeVisible();
      await expect(page.getByText("Tu rol no tiene permiso para ver esta sección.")).toBeVisible();
    }

    await page.getByRole("link", { name: "Volver al inicio" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Inicio" })).toBeVisible();
  });

  test("un paciente inexistente o de otra clínica muestra «Paciente no encontrado»", async ({ page }, testInfo) => {
    // Paciente de Clínica Demo Sur visto por administración de Norte: 404.
    const pacienteSur = await crearPacienteApi(USUARIOS.recepcionSur, {
      first_name: "Paciente",
      last_name: `Sur ${sufijoUnico(testInfo)}`,
    });

    await iniciarSesion(page, USUARIOS.adminNorte);
    await page.goto(`/patients/${pacienteSur}`);

    await expect(page.getByRole("heading", { level: 1, name: "Paciente no encontrado" })).toBeVisible();
    await expect(page.getByText("El paciente no existe o no pertenece a tu clínica.")).toBeVisible();
  });
});
