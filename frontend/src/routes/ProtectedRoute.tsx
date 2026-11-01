import { Navigate, useLocation } from "react-router-dom";

import FullPageLoader from "../components/basic/FullPageLoader";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  const { status, loggedOutManually } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <FullPageLoader />;
  }

  if (status !== "authenticated") {
    // Se recuerda la ruta para volver a ella tras el login, salvo en un cierre voluntario.
    const state = loggedOutManually ? undefined : { from: location.pathname };
    return <Navigate to="/" replace state={state} />;
  }

  return children;
}
