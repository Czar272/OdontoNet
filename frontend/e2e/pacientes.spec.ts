import { expect, test } from "@playwright/test";

import { DOCTORA_NORTE, USUARIOS, iniciarSesion, menu, sufijoUnico } from "./support/helpers";

test.describe("Pacientes", () => {
  test("recepción da de alta un paciente, lo encuentra y abre su ficha", async ({ page }, testInfo) => {
    const nombres = "Lucía Prueba";
    const apellidos = `Alta ${sufijoUnico(testInfo)}`;
    const nombreCompleto = `${nombres} ${apellidos}`;

    await iniciarSesion(page, USUARIOS.recepcionNorte);
    await menu(page).getByRole("link", { name: "Pacientes" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Pacientes" })).toBeVisible();

    await page.getByRole("button", { name: "Nuevo paciente" }).click();
    const dialogo = page.getByRole("dialog", { name: "Nuevo paciente" });
    await dialogo.getByLabel("Nombres *").fill(nombres);
    await dialogo.getByLabel("Apellidos *").fill(apellidos);
    await dialogo.getByLabel("Teléfono").fill("55550000");
    await dialogo.getByLabel("Doctor asignado").selectOption({ label: DOCTORA_NORTE });
    await dialogo.getByRole("button", { name: "Guardar paciente" }).click();

    await expect(page.getByText("Paciente creado")).toBeVisible();
    await expect(dialogo).toBeHidden();

    // Búsqueda en el backend por el apellido único.
    await page.getByLabel("Buscar pacientes").fill(apellidos);
    const enlace = page.getByRole("link", { name: nombreCompleto });
    await expect(enlace).toBeVisible();
    await expect(page.getByRole("row")).toHaveCount(2); // encabezado + el paciente
    await expect(page.getByText("1 paciente ·")).toBeVisible();

    await enlace.click();
    await expect(page).toHaveURL(/\/patients\/\d+$/);
    await expect(page.getByRole("heading", { level: 1, name: nombreCompleto })).toBeVisible();
    await expect(page.getByText(`Doctor asignado: ${DOCTORA_NORTE}`)).toBeVisible();
    await expect(page.getByLabel("Teléfono")).toHaveValue("55550000");
  });
});
