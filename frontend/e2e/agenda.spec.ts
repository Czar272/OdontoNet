import { expect, test } from "@playwright/test";

import {
  DOCTORA_NORTE,
  USUARIOS,
  crearPacienteApi,
  iniciarSesion,
  menu,
  sufijoUnico,
} from "./support/helpers";

const ZONA_CLINICA = "America/Guatemala";
const DIA_MS = 24 * 60 * 60 * 1000;

/**
 * Hueco libre: el lunes de dentro de tres semanas (el seed solo agenda hasta
 * 10 días adelante) en la zona de la clínica, que es la del navegador de prueba.
 */
function lunesEnTresSemanas(): string {
  const hoy = new Intl.DateTimeFormat("en-CA", { timeZone: ZONA_CLINICA }).format(new Date());
  const fecha = new Date(`${hoy}T00:00:00Z`);
  const desdeLunes = (fecha.getUTCDay() + 6) % 7;
  const lunes = new Date(fecha.getTime() + (21 - desdeLunes) * DIA_MS);
  return lunes.toISOString().slice(0, 10);
}

test.describe("Agenda", () => {
  test("recepción agenda una cita y la ve en el calendario", async ({ page }, testInfo) => {
    const apellido = `Agenda ${sufijoUnico(testInfo)}`;
    const paciente = `Paciente ${apellido}`;
    await crearPacienteApi(USUARIOS.adminNorte, { first_name: "Paciente", last_name: apellido });

    const fecha = lunesEnTresSemanas();
    // Dentro del horario demo (8:00–13:00); un reintento usa la hora siguiente.
    const horaBase = String(9 + testInfo.retry).padStart(2, "0");
    const hora = `${horaBase}:00`;

    await iniciarSesion(page, USUARIOS.recepcionNorte);
    await menu(page).getByRole("link", { name: "Agenda" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Agenda" })).toBeVisible();

    await page.getByRole("button", { name: "Nueva cita" }).click();
    const dialogo = page.getByRole("dialog", { name: "Nueva cita" });

    await dialogo.getByLabel("Paciente *").fill(apellido);
    await dialogo
      .getByRole("list", { name: "Resultados de pacientes" })
      .getByRole("button", { name: new RegExp(paciente) })
      .click();
    await expect(dialogo.getByText(paciente)).toBeVisible();

    await dialogo.getByLabel("Doctor *").selectOption({ label: DOCTORA_NORTE });
    await dialogo.getByLabel("Fecha *").fill(fecha);
    await dialogo.getByLabel("Hora *").fill(hora);
    await dialogo.getByLabel("Duración").selectOption({ label: "30 min" });
    await dialogo.getByLabel("Motivo").fill("Control E2E");
    await dialogo.getByRole("button", { name: "Agendar cita" }).click();

    // La doctora atiende de lunes a viernes de 08:00 a 13:00 (seed): un lunes a las
    // 09:00 o 10:00 nunca debe avisar «fuera de horario». Si aparece el aviso, se
    // corrió el horario (zona de la clínica mal interpretada) y la prueba falla.
    const agendada = page.getByText("Cita agendada");
    await expect(agendada).toBeVisible();
    await expect(dialogo.getByRole("button", { name: "Agendar de todas formas" })).toHaveCount(0);
    await expect(dialogo).toBeHidden();

    // Semana de la cita: tres semanas adelante.
    for (let i = 0; i < 3; i++) {
      await page.getByRole("button", { name: "Semana siguiente" }).click();
    }
    const evento = page.locator(".fc-event").filter({ hasText: paciente });
    await expect(evento).toBeVisible();
    await expect(evento).toContainText(`${hora} - ${horaBase}:30 · Programada`);

    // El detalle confirma los datos guardados.
    await evento.click();
    const detalle = page.getByRole("dialog", { name: "Detalle de la cita" });
    await expect(detalle.getByRole("link", { name: paciente })).toBeVisible();
    await expect(detalle).toContainText(DOCTORA_NORTE);
    await expect(detalle).toContainText("Control E2E");
  });
});
