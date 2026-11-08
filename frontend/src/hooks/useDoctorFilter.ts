import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "../context/AuthContext";
import { getDoctors } from "../services/doctorService";

/** "all": todos los doctores · null: aún sin elegir (se usa el valor por defecto). */
export type DoctorChoice = number | "all" | null;

/**
 * Filtro por doctor del panel y los reportes (ODON-202, ODON-206): un doctor
 * arranca enfocado en su propio perfil; los demás, en toda la clínica.
 */
export function useDoctorFilter() {
  const { user } = useAuth();
  const {
    data: doctors,
    isSuccess: doctorsLoaded,
    isError: doctorsFailed,
  } = useQuery({
    queryKey: ["doctors"],
    queryFn: () => getDoctors(),
  });
  const activeDoctors = (doctors ?? []).filter((doctor) => doctor.user.is_active);
  const ownDoctor =
    user?.role === "doctor"
      ? activeDoctors.find((doctor) => doctor.user_id === user.id)
      : undefined;

  const [doctorChoice, setDoctorChoice] = useState<DoctorChoice>(null);
  const doctorId =
    doctorChoice === "all" ? null : (doctorChoice ?? ownDoctor?.id ?? null);
  // Un doctor espera a conocer su perfil para no pedir primero toda la clínica.
  // Si la lista de doctores falla, se muestra toda la clínica en vez de quedar en blanco.
  const ready =
    user?.role !== "doctor" || doctorsLoaded || doctorsFailed || doctorChoice !== null;

  return { activeDoctors, ownDoctor, doctorId, setDoctorChoice, ready };
}
