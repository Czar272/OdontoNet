import { describe, expect, it } from "vitest";

import { toLocalIso } from "./appointmentFormData";
import { confirmationRange } from "./confirmations";

describe("confirmationRange", () => {
  const now = new Date(2026, 10, 10, 15, 42, 30);

  it("va desde este minuto hasta el final del día", () => {
    expect(confirmationRange(1, now)).toEqual({
      start: toLocalIso(new Date(2026, 10, 10, 15, 42)),
      end: toLocalIso(new Date(2026, 10, 11, 0, 0)),
    });
  });

  it("cuenta días completos hacia adelante", () => {
    expect(confirmationRange(7, now).end).toBe(toLocalIso(new Date(2026, 10, 17, 0, 0)));
  });
});
